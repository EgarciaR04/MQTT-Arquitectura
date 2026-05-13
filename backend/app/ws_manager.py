"""Gestor de conexiones WebSocket."""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[user_id].append(ws)
        logger.info("WS conectado: user_id=%s", user_id)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections.get(user_id, []):
                self._connections[user_id].remove(ws)
                if not self._connections[user_id]:
                    del self._connections[user_id]
        logger.info("WS desconectado: user_id=%s", user_id)

    async def send_to_user(self, user_id: int, message: dict) -> None:
        conns = list(self._connections.get(user_id, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("Error enviando WS a user=%s: %s", user_id, e)
                await self.disconnect(user_id, ws)


manager = ConnectionManager()