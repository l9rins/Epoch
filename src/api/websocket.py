import asyncio
import json
from typing import Dict, List, Any
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    """Manages active WebSocket connections for live game monitoring."""
    def __init__(self):
        # Maps game_id -> list of active connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Stores the latest state for each game to serve to new connections immediately
        self.latest_state: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)
        
        # Immediately send the latest state if available
        if game_id in self.latest_state:
            await self.send_personal_message(self.latest_state[game_id], websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        if game_id in self.active_connections:
            if websocket in self.active_connections[game_id]:
                self.active_connections[game_id].remove(websocket)
            if not self.active_connections[game_id]:
                self.active_connections.pop(game_id, None)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    async def broadcast(self, game_id: str, message: dict):
        """Broadcast a message to all clients connected to a specific game."""
        # Cache the latest state (only if it's a STATE update, not just an alert)
        if message.get("type") == "STATE":
            self.latest_state[game_id] = message

        if game_id not in self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections[game_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # Cleanup dead connections
        for dead in dead_connections:
            self.disconnect(dead, game_id)

    def get_connected_count(self, game_id: str) -> int:
        return len(self.active_connections.get(game_id, []))

# Global instance to be imported by main.py and headless_runner.py
manager = ConnectionManager()
