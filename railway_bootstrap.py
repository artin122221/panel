"""
Railway helper: first-run setup (runs after the database migrations, before the panel starts).

Every step is optional and safe to repeat; a step that fails only prints a message.
  1. owner admin      from OWNER_USERNAME / OWNER_PASSWORD (only if no owner exists yet)
  2. core config      "Railway-Xray": one VLESS + WebSocket inbound on 127.0.0.1:10000
  3. node             "Railway-Node": the node running inside this same container
  4. host + group     the public address (RAILWAY_PUBLIC_DOMAIN) users connect to,
                      and a group "Railway-Group" that uses it
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy import select

from app.db.base import GetDB
from app.db.crud.admin import create_admin, get_owner
from app.db.crud.core import create_core_config
from app.db.crud.group import create_group
from app.db.crud.host import create_host
from app.db.crud.node import create_node
from app.db.models import CoreConfig, CoreType, Group, NodeConnectionType, ProxyHost, ProxyHostSecurity
from app.db.models import Node as DBNode
from app.models.admin import AdminCreate
from app.models.core import CoreCreate
from app.models.group import GroupCreate
from app.models.host import CreateHost
from app.models.node import NodeCreate

NODE_DIR = Path(os.environ.get("NODE_DATA_DIR", "/var/lib/pasarguard/node"))
WS_PATH = os.environ.get("XRAY_WS_PATH", "/vless")
INBOUND_TAG = "railway-vless-ws"
CORE_NAME = "Railway-Xray"
NODE_NAME = "Railway-Node"
GROUP_NAME = "Railway-Group"
HOST_REMARK = "Railway VLESS WS"


def xray_config() -> dict:
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": INBOUND_TAG,
                "listen": "127.0.0.1",
                "port": 10000,
                "protocol": "vless",
                "settings": {"clients": [], "decryption": "none"},
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": WS_PATH},
                },
            }
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "DIRECT"},
            {"protocol": "blackhole", "tag": "BLOCK"},
        ],
        "routing": {
            "rules": [{"type": "field", "ip": ["geoip:private"], "outboundTag": "BLOCK"}]
        },
    }


async def step_owner(db) -> None:
    username = os.environ.get("OWNER_USERNAME", "").strip()
    password = os.environ.get("OWNER_PASSWORD", "")
    if not username or not password:
        print("[bootstrap] OWNER_USERNAME / OWNER_PASSWORD not set, skipping owner.")
        return
    if await get_owner(db) is not None:
        print("[bootstrap] owner already exists.")
        return
    await create_admin(db, AdminCreate(username=username, password=password, role_id=1))
    print(f"[bootstrap] owner '{username}' created.")


async def step_core(db) -> int | None:
    core = (await db.execute(select(CoreConfig).where(CoreConfig.name == CORE_NAME))).scalars().first()
    if core is not None:
        return core.id
    core = await create_core_config(
        db,
        CoreCreate(name=CORE_NAME, type=CoreType.xray, config=xray_config()),
    )
    print("[bootstrap] core config created.")
    return core.id


async def step_node(db, core_id: int) -> None:
    exists = (await db.execute(select(DBNode).where(DBNode.name == NODE_NAME))).scalars().first()
    if exists is not None:
        return
    cert = (NODE_DIR / "ssl_cert.pem").read_text()
    api_key = (NODE_DIR / "api_key").read_text().strip()
    await create_node(
        db,
        NodeCreate(
            name=NODE_NAME,
            address="127.0.0.1",
            port=62050,
            api_port=62051,
            connection_type=NodeConnectionType.grpc,
            server_ca=cert,
            keep_alive=0,
            core_config_id=core_id,
            api_key=api_key,
        ),
    )
    print("[bootstrap] node created.")


async def step_host_and_group(db) -> None:
    domain = os.environ.get("HOST_DOMAIN") or os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    domain = domain.strip()
    if not domain:
        print("[bootstrap] no public domain yet (click Generate Domain in Railway); host/group skipped.")
        return

    host = (await db.execute(select(ProxyHost).where(ProxyHost.remark == HOST_REMARK))).scalars().first()
    if host is None:
        await create_host(
            db,
            CreateHost(
                remark=HOST_REMARK,
                address={domain},
                inbound_tag=INBOUND_TAG,
                port=443,
                sni={domain},
                host={domain},
                path=WS_PATH,
                security=ProxyHostSecurity.tls,
                priority=1,
            ),
        )
        print("[bootstrap] host created.")

    group = (await db.execute(select(Group).where(Group.name == GROUP_NAME))).scalars().first()
    if group is None:
        await create_group(db, GroupCreate(name=GROUP_NAME, inbound_tags=[INBOUND_TAG]))
        print("[bootstrap] group created.")


async def main() -> None:
    async with GetDB() as db:
        try:
            await step_owner(db)
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] owner step failed: {exc!r}")

    if os.environ.get("RAILWAY_WITH_NODE", "true").lower() not in ("1", "true", "yes"):
        return

    core_id = None
    async with GetDB() as db:
        try:
            core_id = await step_core(db)
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] core step failed: {exc!r}")

    if core_id is not None:
        async with GetDB() as db:
            try:
                await step_node(db, core_id)
            except Exception as exc:  # noqa: BLE001
                print(f"[bootstrap] node step failed: {exc!r}")

    async with GetDB() as db:
        try:
            await step_host_and_group(db)
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] host/group step failed: {exc!r}")


if __name__ == "__main__":
    asyncio.run(main())
