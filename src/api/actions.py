"""Action logging and retrieval endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.database import get_db_session, Action


router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.get("/recent")
async def get_recent_actions(
    limit: int = Query(50, ge=1, le=500),
    classification: Optional[str] = None,
    decision: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> list[dict]:
    """Get recent logged actions with filters.

    Args:
        limit: Number of actions to return.
        classification: Filter by classification (green/yellow/red).
        decision: Filter by decision (approved/blocked/flagged).
        agent_id: Filter by agent ID.

    Returns:
        List of action records.
    """
    try:
        session = get_db_session()

        query = session.query(Action).order_by(Action.timestamp.desc())

        # Apply filters
        if classification:
            query = query.filter_by(classification=classification)
        if decision:
            query = query.filter_by(decision=decision)
        if agent_id:
            query = query.filter_by(agent_id=agent_id)

        actions = query.limit(limit).all()

        session.close()

        return [action.to_dict() for action in actions]

    except Exception as e:
        print(f"Error getting recent actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-agent/{agent_id}")
async def get_agent_actions(
    agent_id: str,
    limit: int = Query(50, ge=1, le=500),
    hours: int = Query(24, ge=1, le=720),
) -> list[dict]:
    """Get actions for a specific agent.

    Args:
        agent_id: Agent ID.
        limit: Number of actions to return.
        hours: Look back this many hours.

    Returns:
        List of action records.
    """
    try:
        session = get_db_session()

        since = datetime.utcnow() - timedelta(hours=hours)

        actions = (
            session.query(Action)
            .filter_by(agent_id=agent_id)
            .filter(Action.timestamp >= since)
            .order_by(Action.timestamp.desc())
            .limit(limit)
            .all()
        )

        session.close()

        return [action.to_dict() for action in actions]

    except Exception as e:
        print(f"Error getting agent actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocked")
async def get_blocked_actions(
    limit: int = Query(50, ge=1, le=500),
    days: int = Query(7, ge=1, le=90),
) -> list[dict]:
    """Get blocked actions.

    Args:
        limit: Number of actions to return.
        days: Look back this many days.

    Returns:
        List of blocked action records.
    """
    try:
        from src.database import BlockedAction

        session = get_db_session()

        since = datetime.utcnow() - timedelta(days=days)

        blocked = (
            session.query(BlockedAction)
            .filter(BlockedAction.blocked_at >= since)
            .order_by(BlockedAction.blocked_at.desc())
            .limit(limit)
            .all()
        )

        session.close()

        return [action.to_dict() for action in blocked]

    except Exception as e:
        print(f"Error getting blocked actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
) -> list[dict]:
    """Get alerts for red/dangerous actions.

    Args:
        limit: Number of alerts to return.
        severity: Filter by severity (critical/high/medium).
        days: Look back this many days.

    Returns:
        List of alert records.
    """
    try:
        from src.database import AlertLog

        session = get_db_session()

        since = datetime.utcnow() - timedelta(days=days)

        query = session.query(AlertLog).filter(AlertLog.created_at >= since)

        if severity:
            query = query.filter_by(severity=severity)

        alerts = query.order_by(AlertLog.created_at.desc()).limit(limit).all()

        session.close()

        return [alert.to_dict() for alert in alerts]

    except Exception as e:
        print(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{action_id}")
async def get_action(action_id: str) -> dict:
    """Get a specific action by ID.

    Args:
        action_id: Action ID.

    Returns:
        Action record.
    """
    try:
        session = get_db_session()

        action = session.query(Action).filter_by(action_id=action_id).first()

        session.close()

        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        return action.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-reviewed/{action_id}")
async def mark_reviewed(action_id: str, approved: bool, reason: Optional[str] = None) -> dict:
    """Mark a blocked action as reviewed.

    Args:
        action_id: Action ID.
        approved: Whether the action is approved.
        reason: Approval reason.

    Returns:
        Updated blocked action record.
    """
    try:
        from src.database import BlockedAction

        session = get_db_session()

        blocked = session.query(BlockedAction).filter_by(action_id=action_id).first()

        if not blocked:
            raise HTTPException(status_code=404, detail="Blocked action not found")

        blocked.approved = approved
        blocked.approval_reason = reason
        blocked.reviewed_at = datetime.utcnow()

        session.commit()

        result = blocked.to_dict()
        session.close()

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error marking action reviewed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
