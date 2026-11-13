# Railway version of the PasarGuard panel Dockerfile (panel + node + Xray in ONE container).
# Differences from the original (kept as Dockerfile.original):
#   1) the compiled dashboard is copied from the official panel image of the SAME version
#      (the original CI does the same: the dashboard is prebuilt, not built at runtime);
#   2) the official node program and Xray are copied from the official node image;
#   3) nginx shares the single public port between the panel and the Xray WebSocket;
#   4) plain HTTP is allowed, because Railway provides HTTPS itself.
ARG PYTHON_VERSION=3.14
ARG PANEL_IMAGE=pasarguard/panel:v5.6.0
ARG NODE_IMAGE=pasarguard/node:v0.5.7

FROM ${PANEL_IMAGE} AS official-panel
FROM ${NODE_IMAGE} AS official-node

FROM ghcr.io/astral-sh/uv:python$PYTHON_VERSION-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /build
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
ADD . /build
COPY --from=official-panel /code/dashboard/build /build/dashboard/build
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:$PYTHON_VERSION-slim-bookworm

COPY --from=builder /build /code
WORKDIR /code

ENV PATH="/code/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    nginx \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node program + Xray (from the official node image)
COPY --from=official-node /app/main /usr/local/bin/pg-node
COPY --from=official-node /usr/local/bin/xray /usr/local/bin/xray
COPY --from=official-node /usr/local/share/xray /usr/local/share/xray

COPY cli_wrapper.sh /usr/bin/pasarguard-cli
RUN chmod +x /usr/bin/pasarguard-cli

COPY tui_wrapper.sh /usr/bin/pasarguard-tui
RUN chmod +x /usr/bin/pasarguard-tui

COPY healthcheck.sh /code/healthcheck.sh
RUN chmod +x /code/healthcheck.sh

RUN chmod +x /code/start.sh /usr/local/bin/pg-node /usr/local/bin/xray

# --- Railway settings ---
RUN mkdir -p /var/lib/pasarguard
ENV RAILWAY_WITH_NODE=true \
    ALLOW_PLAIN_HTTP=true \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PROXY_HEADERS=true \
    UVICORN_FORWARDED_ALLOW_IPS=* \
    SQLALCHEMY_DATABASE_URL=sqlite+aiosqlite:////var/lib/pasarguard/db.sqlite3

ENTRYPOINT ["/code/start.sh"]
