"""WebSocket endpoints for real-time action streaming and dashboard updates."""

import asyncio
import json
from datetime import datetime
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from src.database import get_db_manager
from src.schemas import ActionType

# Track connected clients
connected_clients: Set[WebSocket] = set()
action_queue = asyncio.Queue()

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Add a new connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected client."""
        self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass  # Connection already closed


manager = ConnectionManager()


@router.websocket("/actions/stream")
async def websocket_action_stream(
    websocket: WebSocket,
    agent_id: str = Query(None),
    classification: str = Query(None),
):
    """
    WebSocket endpoint for real-time action stream.

    Streams all logged actions as they occur with live updates.

    Args:
        websocket: WebSocket connection
        agent_id: Optional filter by agent ID
        classification: Optional filter by classification (green/yellow/red)

    Example:
        ws://localhost:8000/ws/actions/stream?agent_id=claude-dev&classification=red
    """
    await manager.connect(websocket)

    try:
        db = get_db_manager()

        while True:
            # Send initial actions
            query = "SELECT * FROM actions ORDER BY created_at DESC LIMIT 100"
            if agent_id:
                query += f" AND agent_id = '{agent_id}'"
            if classification:
                query += f" AND classification = '{classification}'"

            actions = db.fetch_all(query)

            # Format actions for streaming
            action_data = []
            for action in actions:
                action_data.append(
                    {
                        "action_id": action.get("action_id"),
                        "agent_id": action.get("agent_id"),
                        "action_type": action.get("action_type"),
                        "command": action.get("command"),
                        "target_resource": action.get("target_resource"),
                        "classification": action.get("classification"),
                        "confidence": float(action.get("confidence", 0)),
                        "decision": action.get("decision"),
                        "reason": action.get("reason"),
                        "timestamp": action.get("created_at").isoformat()
                        if action.get("created_at")
                        else None,
                        "duration_ms": float(action.get("duration_ms", 0)),
                    }
                )

            # Send batch of recent actions
            await websocket.send_json(
                {
                    "type": "action_batch",
                    "actions": action_data[:50],
                    "count": len(action_data),
                }
            )

            # Wait for new actions (poll every 500ms)
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/agents/{agent_id}/graph")
async def websocket_blast_radius(websocket: WebSocket, agent_id: str):
    """
    WebSocket endpoint for blast radius map updates.

    Streams real-time graph of resources touched by agent.

    Args:
        websocket: WebSocket connection
        agent_id: Agent to track

    Returns:
        Graph data with nodes (files/tables/services) and edges (relationships)
    """
    await manager.connect(websocket)

    try:
        db = get_db_manager()

        while True:
            # Get all actions for this agent
            actions = db.fetch_all(
                f"""
                SELECT DISTINCT target_resource, action_type, classification
                FROM actions
                WHERE agent_id = '{agent_id}'
                ORDER BY created_at DESC
                LIMIT 1000
            """
            )

            # Build graph: nodes and edges
            nodes = {}
            edges = []

            for i, action in enumerate(actions):
                resource = action.get("target_resource", "unknown")
                action_type = action.get("action_type", "unknown")
                classification = action.get("classification", "green")

                # Add node
                if resource not in nodes:
                    # Determine resource type
                    if resource.startswith("/"):
                        res_type = "file"
                        if resource.endswith(".db"):
                            res_type = "database"
                        elif "backup" in resource:
                            res_type = "backup"
                    elif "." in resource and "@" in resource:
                        res_type = "api_call"
                    else:
                        res_type = "unknown"

                    nodes[resource] = {
                        "id": resource,
                        "label": resource.split("/")[-1] or resource,
                        "type": res_type,
                        "classification": classification,
                        "action_count": 1,
                    }
                else:
                    nodes[resource]["action_count"] += 1

                # Add edges to previous nodes
                if i > 0 and i < len(actions):
                    prev_resource = actions[i - 1].get("target_resource")
                    if prev_resource and prev_resource != resource:
                        edges.append(
                            {
                                "source": resource,
                                "target": prev_resource,
                                "type": action_type,
                            }
                        )

            # Send graph update
            await websocket.send_json(
                {
                    "type": "graph_update",
                    "agent_id": agent_id,
                    "nodes": list(nodes.values()),
                    "edges": edges[:50],  # Limit edges for performance
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # Update every second
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket graph error: {e}")
        manager.disconnect(websocket)


@router.websocket("/agents/{agent_id}/timeline")
async def websocket_rollback_timeline(websocket: WebSocket, agent_id: str):
    """
    WebSocket endpoint for rollback timeline.

    Streams action timeline with rollback preview.

    Args:
        websocket: WebSocket connection
        agent_id: Agent to track

    Returns:
        Timeline events with rollback options
    """
    await manager.connect(websocket)

    try:
        db = get_db_manager()

        while True:
            # Get all actions for timeline
            actions = db.fetch_all(
                f"""
                SELECT
                    action_id,
                    created_at,
                    action_type,
                    command,
                    target_resource,
                    classification,
                    decision
                FROM actions
                WHERE agent_id = '{agent_id}'
                ORDER BY created_at ASC
                LIMIT 500
            """
            )

            timeline = []
            for i, action in enumerate(actions):
                timeline.append(
                    {
                        "index": i,
                        "action_id": action.get("action_id"),
                        "timestamp": action.get("created_at").isoformat()
                        if action.get("created_at")
                        else None,
                        "action_type": action.get("action_type"),
                        "command": action.get("command"),
                        "target": action.get("target_resource"),
                        "classification": action.get("classification"),
                        "decision": action.get("decision"),
                        "can_rollback": action.get("decision") != "approved"
                        or action.get("classification") in ["yellow", "red"],
                    }
                )

            # Send timeline
            await websocket.send_json(
                {
                    "type": "timeline_update",
                    "agent_id": agent_id,
                    "timeline": timeline,
                    "total_actions": len(timeline),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # Update every second
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket timeline error: {e}")
        manager.disconnect(websocket)


@router.get("/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    return {
        "connected_clients": len(manager.active_connections),
        "timestamp": datetime.utcnow().isoformat(),
    }
