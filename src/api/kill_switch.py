"""Kill switch API endpoints - Layer 6."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.layers import get_kill_switch
from src.slack_bot import get_slack_bot


router = APIRouter(prefix="/api/agents", tags=["kill-switch"])


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str) -> dict:
    """Get agent status.

    Args:
        agent_id: Agent ID.

    Returns:
        Agent status.
    """
    try:
        kill_switch = get_kill_switch()
        status = kill_switch.get_agent_status(agent_id)

        if not status:
            return {
                "agent_id": agent_id,
                "status": "unknown",
                "error": "Agent not found",
            }

        return status

    except Exception as e:
        print(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/halt")
async def halt_agent(
    agent_id: str,
    reason: str = Query(...),
    initiated_by: str = Query("system"),
    generate_rollback: bool = Query(True),
) -> dict:
    """Halt an agent immediately (Kill Switch).

    Args:
        agent_id: Agent to halt.
        reason: Reason for halt.
        initiated_by: User or system halting.
        generate_rollback: Whether to auto-generate compensating transactions.

    Returns:
        Halt result with timing and ID.
    """
    try:
        kill_switch = get_kill_switch()
        success, halt_time_ms, halt_id = kill_switch.halt_agent(
            agent_id=agent_id,
            initiated_by=initiated_by,
            reason=reason,
            initiated_via="api",
            generate_compensating_tx=generate_rollback,
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to halt agent")

        # Notify Slack
        slack_bot = get_slack_bot()
        slack_bot.notify_halt_event(agent_id, initiated_by, reason, halt_time_ms, halt_id)

        return {
            "agent_id": agent_id,
            "halted": True,
            "halt_id": halt_id,
            "halt_time_ms": halt_time_ms,
            "reason": reason,
            "initiated_by": initiated_by,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error halting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/resume")
async def resume_agent(
    agent_id: str,
    resumed_by: str = Query("system"),
) -> dict:
    """Resume a halted agent.

    Args:
        agent_id: Agent to resume.
        resumed_by: User resuming the agent.

    Returns:
        Resume result.
    """
    try:
        kill_switch = get_kill_switch()
        success = kill_switch.resume_agent(
            agent_id=agent_id,
            resumed_by=resumed_by,
            reason="Resumed via API",
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to resume agent")

        return {
            "agent_id": agent_id,
            "resumed": True,
            "resumed_by": resumed_by,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error resuming agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/halted")
async def get_halted_agents() -> dict:
    """Get all currently halted agents.

    Returns:
        List of halted agents.
    """
    try:
        kill_switch = get_kill_switch()
        agents = kill_switch.get_halted_agents()

        return {
            "halted_agents": agents,
            "count": len(agents),
        }

    except Exception as e:
        print(f"Error getting halted agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/halt-history")
async def get_halt_history(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Get halt history for an agent.

    Args:
        agent_id: Agent ID.
        limit: Max records to return.

    Returns:
        List of halt events.
    """
    try:
        kill_switch = get_kill_switch()
        history = kill_switch.get_halt_history(agent_id, limit)

        return {
            "agent_id": agent_id,
            "halt_events": history,
            "count": len(history),
        }

    except Exception as e:
        print(f"Error getting halt history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Slack integration endpoint
slack_router = APIRouter(prefix="/slack", tags=["slack"])


@slack_router.post("/commands/agentfuse")
async def handle_slack_command(payload: dict) -> dict:
    """Handle Slack slash command /agentfuse.

    Args:
        payload: Slack command payload.

    Returns:
        Slack response.
    """
    try:
        slack_bot = get_slack_bot()
        response = slack_bot.handle_slash_command(payload)
        return response

    except Exception as e:
        print(f"Error handling Slack command: {e}")
        return {
            "response_type": "ephemeral",
            "text": f"❌ Error: {str(e)}",
        }


@slack_router.post("/events")
async def handle_slack_events(payload: dict) -> dict:
    """Handle Slack events (for button clicks, etc).

    Args:
        payload: Slack event payload.

    Returns:
        Slack response.
    """
    # Handle button clicks and interactive events
    if payload.get("type") == "block_actions":
        actions = payload.get("actions", [])
        user_id = payload.get("user", {}).get("id")

        for action in actions:
            if action.get("action_id") == "resume_agent":
                agent_id = action.get("value")
                kill_switch = get_kill_switch()
                kill_switch.resume_agent(agent_id=agent_id, resumed_by=user_id)

                return {
                    "text": f"✅ Agent `{agent_id}` resumed",
                }

    return {"ok": True}


# Global halt events endpoint
@router.get("/halt-events")
async def get_recent_halt_events(
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Get recent halt events across all agents.

    Args:
        limit: Max records to return.

    Returns:
        List of halt events.
    """
    try:
        kill_switch = get_kill_switch()
        events = kill_switch.get_recent_halt_events(limit)

        return {
            "halt_events": events,
            "count": len(events),
        }

    except Exception as e:
        print(f"Error getting halt events: {e}")
        raise HTTPException(status_code=500, detail=str(e))
