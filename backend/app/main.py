"""Aplicación principal de FastAPI."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.auth import decode_token
from app.config import settings
from app.database import init_db
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
    version="0.1.0",
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


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    try:
        user_id = decode_token(token)
    except Exception:
        await ws.close(code=1008, reason="Token inválido")
        return

    await manager.connect(user_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, ws)
    except Exception:
        await manager.disconnect(user_id, ws)