#!/usr/bin/env bash

ROLE="${ROLE:-all-in-one}"

if [ "${ROLE}" = "node" ]; then
    exec python node_worker.py
elif [ "${ROLE}" = "scheduler" ]; then
    exec python scheduler_worker.py
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting ${ROLE}..."
    python -m alembic upgrade head
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Database migrations failed"
        exit 1
    fi

    if [ "${RAILWAY_WITH_NODE:-false}" = "true" ] && [ -x /usr/local/bin/pg-node ]; then
        # ---- Railway all-in-one mode: panel + node + Xray in one container ----
        PUBLIC_PORT="${PORT:-8080}"
        PANEL_PORT=8000
        if [ "${PUBLIC_PORT}" = "${PANEL_PORT}" ]; then PANEL_PORT=8001; fi
        NODE_DATA_DIR="${NODE_DATA_DIR:-/var/lib/pasarguard/node}"
        XRAY_WS_PATH="${XRAY_WS_PATH:-/vless}"
        export NODE_DATA_DIR XRAY_WS_PATH

        # 1) certificate + api key for the local node (created once, kept in the volume)
        python railway_prepare.py || echo "[prepare] failed"

        # 2) start the node (Xray runs inside it), listening only inside the container
        (
            cd "${NODE_DATA_DIR}" || exit 1
            export API_KEY="$(cat "${NODE_DATA_DIR}/api_key")"
            export SERVICE_PORT=62050 NODE_HOST=127.0.0.1 SERVICE_PROTOCOL=grpc
            export SSL_CERT_FILE="${NODE_DATA_DIR}/ssl_cert.pem"
            export SSL_KEY_FILE="${NODE_DATA_DIR}/ssl_key.pem"
            export GENERATED_CONFIG_PATH="${NODE_DATA_DIR}/generated/"
            export PG_NODE_WG_HOST_ROUTING=0
            exec /usr/local/bin/pg-node
        ) &

        # 3) nginx on the public port: Xray WebSocket path -> Xray, everything else -> panel
        sed -e "s#__PORT__#${PUBLIC_PORT}#g" -e "s#__PANEL_PORT__#${PANEL_PORT}#g" -e "s#__WS_PATH__#${XRAY_WS_PATH}#g" \
            /code/railway-nginx.conf > /etc/nginx/railway.conf
        nginx -c /etc/nginx/railway.conf &

        # 4) the panel itself listens only inside the container
        export UVICORN_HOST=127.0.0.1
        export UVICORN_PORT="${PANEL_PORT}"
        export UVICORN_PROXY_HEADERS=true
        export UVICORN_FORWARDED_ALLOW_IPS="*"
    elif [ -n "${PORT}" ]; then
        # Railway without node: the panel itself uses the port Railway gives
        export UVICORN_PORT="${PORT}"
    fi

    # Create the owner admin (and, in all-in-one mode, the node/core/host/group) on first run.
    python railway_bootstrap.py || echo "[bootstrap] skipped"

    exec python main.py
fi
