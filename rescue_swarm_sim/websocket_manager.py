from fastapi import WebSocket
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.loop = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

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
            print(f"Error: No running event loop to broadcast {msg_type}")
