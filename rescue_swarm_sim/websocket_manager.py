from fastapi import WebSocket
import asyncio
import logging

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.loop = None
        self._log = logging.getLogger("ws")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self._log.info(f"WS connected. Active={len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self._log.info(f"WS disconnected. Active={len(self.active_connections)}")

    async def broadcast(self, message: dict):
        self._log.debug(f"Broadcasting to {len(self.active_connections)} connections: {message.get('type')}")
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:
                if connection in self.active_connections:
                    self.active_connections.remove(connection)
                    self._log.warning(f"Removed dead WS. Active={len(self.active_connections)}")

manager = ConnectionManager()

def send_to_ui(msg_type: str, payload: dict):
    """A thread-safe helper to push data to the React UI."""
    message = {"type": msg_type, "payload": payload}
    
    if manager.loop and manager.loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), manager.loop)
    else:
        # Fallback if loop wasn't captured yet
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)
        except RuntimeError:
            logging.getLogger("ws").error(f"No running event loop to broadcast {msg_type}")
