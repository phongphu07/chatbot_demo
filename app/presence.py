import json
import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class PresenceManager:
    """
    True Real-Time Presence Hub hỗ trợ cả WebSocket 2 chiều và SSE stream/Beacon.
    Phát hiện kết nối và ngắt kết nối (đóng tab) tức thì (< 20ms).
    """
    def __init__(self):
        self._connected_sockets: Dict[str, Set[WebSocket]] = {}
        self._sse_queues: Dict[str, Set[asyncio.Queue]] = {}
        self._active_clients: Set[str] = set()
        self._lock = asyncio.Lock()
        self._simulated_base: int = 0

    @property
    def online_count(self) -> int:
        unique_clients = set(self._connected_sockets.keys()) | set(self._sse_queues.keys()) | self._active_clients
        return max(1, len(unique_clients) + self._simulated_base)

    async def connect_ws(self, client_id: str, websocket: WebSocket):
        """Khi có tab mới mở ra qua WebSocket"""
        async with self._lock:
            if client_id not in self._connected_sockets:
                self._connected_sockets[client_id] = set()
            self._connected_sockets[client_id].add(websocket)
            current_count = self.online_count

        logger.info(f"[WebSocket Presence] Client {client_id} connected. Online count: {current_count}")
        await self._broadcast(current_count)

    async def disconnect_ws(self, client_id: str, websocket: WebSocket):
        """Khi tab đóng lại qua WebSocket"""
        async with self._lock:
            if client_id in self._connected_sockets:
                self._connected_sockets[client_id].discard(websocket)
                if not self._connected_sockets[client_id]:
                    del self._connected_sockets[client_id]
            current_count = self.online_count

        logger.info(f"[WebSocket Presence] Client {client_id} disconnected. Online count: {current_count}")
        await self._broadcast(current_count)

    async def register(self, client_id: str) -> asyncio.Queue:
        """Đăng ký client kết nối qua SSE stream"""
        queue = asyncio.Queue()
        async with self._lock:
            if client_id not in self._sse_queues:
                self._sse_queues[client_id] = set()
            self._sse_queues[client_id].add(queue)
            current_count = self.online_count

        logger.info(f"[SSE Presence] Client {client_id} registered. Online count: {current_count}")
        await self._broadcast(current_count)
        return queue

    async def unregister(self, client_id: str, queue: asyncio.Queue):
        """Hủy đăng ký client SSE stream khi ngắt kết nối"""
        async with self._lock:
            if client_id in self._sse_queues:
                self._sse_queues[client_id].discard(queue)
                if not self._sse_queues[client_id]:
                    del self._sse_queues[client_id]
            current_count = self.online_count

        logger.info(f"[SSE Presence] Client {client_id} unregistered. Online count: {current_count}")
        await self._broadcast(current_count)

    async def leave(self, client_id: str):
        """Xử lý sự kiện đóng tab khi client gửi navigator.sendBeacon('/api/presence/leave')"""
        async with self._lock:
            if client_id in self._connected_sockets:
                del self._connected_sockets[client_id]
            if client_id in self._sse_queues:
                del self._sse_queues[client_id]
            if client_id in self._active_clients:
                self._active_clients.discard(client_id)
            current_count = self.online_count

        logger.info(f"[Presence] Client {client_id} left via beacon. Online count: {current_count}")
        await self._broadcast(current_count)

    async def _broadcast(self, count: int):
        """Phát thông báo số đếm tới toàn bộ WebSocket và SSE stream"""
        ws_msg = json.dumps({"type": "presence_update", "active_users": count})
        sse_msg = json.dumps({"active_users": count})

        async with self._lock:
            all_sockets = [ws for sockets in self._connected_sockets.values() for ws in sockets]
            all_queues = [q for queues in self._sse_queues.values() for q in queues]

        for ws in all_sockets:
            try:
                await ws.send_text(ws_msg)
            except Exception:
                pass

        for q in all_queues:
            try:
                q.put_nowait(sse_msg)
            except Exception:
                pass

    def get_online_count(self) -> int:
        return self.online_count

    def ping(self, client_id: str, is_active: bool = False) -> int:
        self._active_clients.add(client_id)
        return self.online_count

presence_manager = PresenceManager()
