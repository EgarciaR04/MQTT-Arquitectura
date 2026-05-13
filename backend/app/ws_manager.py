"""Gestor de conexiones WebSocket por dispositivo."""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Cada conexión WS se asocia a un device_id específico.
    Solo recibe los eventos de ese dispositivo.
    """

    def __init__(self) -> None:
        self._by_device: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, device_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._by_device[device_id].append(ws)
        logger.info("WS conectado: device_id=%s (total=%d)",
                    device_id, len(self._by_device[device_id]))

    async def disconnect(self, device_id: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._by_device.get(device_id, [])
            if ws in conns:
                conns.remove(ws)
                if not conns:
                    del self._by_device[device_id]
        logger.info("WS desconectado: device_id=%s", device_id)

    async def send_to_device(self, device_id: str, message: dict) -> None:
        """Envía un mensaje a TODAS las conexiones suscritas a ese dispositivo."""
        conns = list(self._by_device.get(device_id, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("Error enviando WS de %s: %s", device_id, e)
                await self.disconnect(device_id, ws)


manager = ConnectionManager()