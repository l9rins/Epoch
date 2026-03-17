"""
src/api/websocket.py
WebSocket connection manager with:
- Per-game channels + global LIVE_FEED channel
- Signal broadcasting from AlertEngine
- Ping/pong keepalive (30s)
- Graceful dead connection cleanup
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, List, Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Global channel name for all clients who want the live signal feed
LIVE_FEED_CHANNEL = "LIVE_FEED"
PING_INTERVAL_S   = 30


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Channels:
      - "LIVE_FEED"   — all clients wanting the global signal feed
      - "{game_id}"   — clients watching a specific game
    """

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.latest_state: Dict[str, dict] = {}
        self._ping_task: asyncio.Task | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

        # Send latest cached state immediately on connect
        if channel in self.latest_state:
            await self._safe_send(websocket, self.latest_state[channel])

        total = sum(len(v) for v in self.active_connections.values())
        logger.info(f"ws: client connected to '{channel}' — {total} total connections")

        # Start ping task if not running
        if self._ping_task is None or self._ping_task.done():
            self._ping_task = asyncio.create_task(self._ping_loop())

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            try:
                self.active_connections[channel].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[channel]:
                self.active_connections.pop(channel, None)

        total = sum(len(v) for v in self.active_connections.values())
        logger.info(f"ws: client disconnected from '{channel}' — {total} total connections")

    # ── Broadcasting ──────────────────────────────────────────────────────────

    async def broadcast(self, channel: str, message: dict):
        """Broadcast to all clients in a channel."""
        # Cache state messages for late joiners
        if message.get("type") in ("STATE", "PREDICTION_UPDATE"):
            self.latest_state[channel] = message

        if channel not in self.active_connections:
            return

        dead = []
        for ws in list(self.active_connections[channel]):
            success = await self._safe_send(ws, message)
            if not success:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws, channel)

    async def broadcast_signal(self, signal: dict):
        """
        Broadcast a signal alert to LIVE_FEED channel.
        Called by the signal engine when alerts fire.

        signal shape:
        {
            "type": "ALERT",
            "alert_type": "WIN_PROB_THRESHOLD" | "MOMENTUM_SHIFT" | "PREGAME_EDGE" | ...,
            "tier": 1 | 2 | 3,
            "message": str,
            "value": float,
            "timestamp": float,
            "game_id": str (optional),
        }
        """
        message = {
            "type":       "ALERT",
            "tier":       signal.get("tier", 3),
            "alert_type": signal.get("alert_type", "SIGNAL"),
            "message":    signal.get("message", ""),
            "value":      signal.get("value"),
            "timestamp":  signal.get("timestamp", time.time()),
            "game_id":    signal.get("game_id"),
            "time_ago":   "JUST NOW",
        }

        # Broadcast to global feed
        await self.broadcast(LIVE_FEED_CHANNEL, message)

        # Also broadcast to game-specific channel if game_id provided
        game_id = signal.get("game_id")
        if game_id:
            await self.broadcast(game_id, message)

    async def broadcast_prediction(self, prediction: dict):
        """
        Broadcast a prediction update.
        Called by /api/predict after ensemble runs.
        """
        game_id = prediction.get("game_id", LIVE_FEED_CHANNEL)
        message = {
            "type":    "PREDICTION_UPDATE",
            "payload": prediction,
        }
        await self.broadcast(LIVE_FEED_CHANNEL, message)
        await self.broadcast(game_id, message)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _safe_send(self, websocket: WebSocket, message: dict) -> bool:
        """Send message, return False if connection is dead."""
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            return False

    async def _ping_loop(self):
        """Keep connections alive with periodic pings."""
        while True:
            await asyncio.sleep(PING_INTERVAL_S)
            if not self.active_connections:
                continue
            ping = {"type": "PING", "timestamp": time.time()}
            dead_channels = []
            for channel, connections in list(self.active_connections.items()):
                dead = []
                for ws in list(connections):
                    success = await self._safe_send(ws, ping)
                    if not success:
                        dead.append(ws)
                for ws in dead:
                    self.disconnect(ws, channel)
                if not self.active_connections.get(channel):
                    dead_channels.append(channel)
            for ch in dead_channels:
                self.active_connections.pop(ch, None)

    def get_connected_count(self, channel: str = None) -> int:
        if channel:
            return len(self.active_connections.get(channel, []))
        return sum(len(v) for v in self.active_connections.values())

    def get_channels(self) -> list:
        return list(self.active_connections.keys())


# Global singleton
manager = ConnectionManager()
