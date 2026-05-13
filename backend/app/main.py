"""Aplicación principal de FastAPI."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.auth import decode_token
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import Device
from app.mqtt_handler import mqtt_lifespan
from app.routers import auth_router, devices_router
from app.ws_manager import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando aplicación...")
    await init_db()
    async with mqtt_lifespan():
        yield
    logger.info("Aplicación cerrada")


app = FastAPI(
    title="IoT Backend",
    version="0.2.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(devices_router.router)


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "iot-backend"}


@app.websocket("/ws/{device_id}")
async def websocket_endpoint(
    ws: WebSocket,
    device_id: str,
    token: str = Query(..., description="JWT del usuario"),
):
    """
    WebSocket por dispositivo.
    Uso: /ws/{device_id}?token=<JWT>
    Solo emite eventos de telemetría y estado del dispositivo indicado,
    siempre que pertenezca al usuario autenticado.
    """
    # 1. Validar token
    try:
        user_id = decode_token(token)
    except Exception:
        await ws.close(code=1008, reason="Token inválido")
        return

    # 2. Verificar que el dispositivo existe y es del usuario
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Device).where(
                Device.device_id == device_id,
                Device.owner_id == user_id,
            )
        )
        device = result.scalar_one_or_none()
        if device is None:
            await ws.close(code=1008, reason="Dispositivo no encontrado o no autorizado")
            return

    # 3. Registrar la conexión bajo el device_id
    await manager.connect(device_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(device_id, ws)
    except Exception as e:
        logger.warning("Error WS device=%s: %s", device_id, e)
        await manager.disconnect(device_id, ws)