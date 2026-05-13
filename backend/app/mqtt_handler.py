"""Cliente MQTT del backend: suscribe a telemetría, persiste, publica comandos."""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import aiomqtt
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Device, Telemetry
from app.ws_manager import manager

logger = logging.getLogger(__name__)

_client: aiomqtt.Client | None = None
_publish_lock = asyncio.Lock()


async def publish_command(device_id: str, payload: dict[str, Any]) -> bool:
    global _client
    if _client is None:
        logger.error("Cliente MQTT no inicializado")
        return False

    topic = f"devices/{device_id}/commands"
    message = json.dumps(payload)
    async with _publish_lock:
        await _client.publish(topic, message, qos=1)
    logger.info("Comando publicado en %s: %s", topic, message)
    return True


async def _handle_telemetry(device_id_str: str, payload_raw: bytes) -> None:
    try:
        payload = json.loads(payload_raw.decode())
    except json.JSONDecodeError:
        logger.warning("Payload no es JSON válido (%s)", device_id_str)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Device).where(Device.device_id == device_id_str)
        )
        device = result.scalar_one_or_none()
        if device is None:
            logger.warning("Telemetría de dispositivo desconocido: %s", device_id_str)
            return

        record = Telemetry(device_id=device.id, payload=payload)
        db.add(record)
        await db.commit()
        await db.refresh(record)

        await manager.send_to_device(
            device.device_id,
            {
                "type": "telemetry",
                "device_id": device.device_id,
                "timestamp": record.timestamp.isoformat(),
                "payload": payload,
            },
        )


async def _handle_status(device_id_str: str, payload_raw: bytes) -> None:
    status_value = payload_raw.decode(errors="replace")
    logger.info("Estado %s = %s", device_id_str, status_value)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Device).where(Device.device_id == device_id_str)
        )
        device = result.scalar_one_or_none()
        if device is None:
            return
        await manager.send_to_device(
            device.device_id,
            {"type": "status", "device_id": device.device_id, "status": status_value},
        )


async def _process_message(topic: str, payload: bytes) -> None:
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != "devices":
        return
    device_id_str, kind = parts[1], parts[2]
    if kind == "telemetry":
        await _handle_telemetry(device_id_str, payload)
    elif kind == "status":
        await _handle_status(device_id_str, payload)


@asynccontextmanager
async def mqtt_lifespan():
    global _client
    stop_event = asyncio.Event()

    async def run() -> None:
        global _client
        while not stop_event.is_set():
            try:
                async with aiomqtt.Client(
                    hostname=settings.mqtt_host,
                    port=settings.mqtt_port,
                    username=settings.mqtt_user,
                    password=settings.mqtt_pass,
                ) as client:
                    _client = client
                    logger.info("Conectado al broker MQTT en %s:%s",
                                settings.mqtt_host, settings.mqtt_port)
                    await client.subscribe("devices/+/telemetry", qos=1)
                    await client.subscribe("devices/+/status", qos=1)

                    async for message in client.messages:
                        await _process_message(str(message.topic), message.payload)
            except aiomqtt.MqttError as e:
                logger.error("Conexión MQTT perdida: %s. Reintento en 5s", e)
                _client = None
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    task = asyncio.create_task(run())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        _client = None