"""Snapshot and rollback API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.layers import get_snapshot_store, get_rollback_engine


router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("/action/{action_id}")
async def get_action_snapshots(action_id: str) -> list[dict]:
    """Get all snapshots for an action.

    Args:
        action_id: Action ID.

    Returns:
        List of snapshot records.
    """
    try:
        snapshot_store = get_snapshot_store()
        snapshots = snapshot_store.get_action_snapshots(action_id)
        return snapshots

    except Exception as e:
        print(f"Error getting action snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str) -> dict:
    """Get a specific snapshot.

    Args:
        snapshot_id: Snapshot ID.

    Returns:
        Snapshot metadata and content.
    """
    try:
        snapshot_store = get_snapshot_store()
        snapshot = snapshot_store.get_snapshot(snapshot_id)

        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        return snapshot

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{snapshot_id}/verify")
async def verify_snapshot_integrity(snapshot_id: str) -> dict:
    """Verify snapshot content integrity.

    Args:
        snapshot_id: Snapshot ID.

    Returns:
        Verification result.
    """
    try:
        snapshot_store = get_snapshot_store()
        is_valid = snapshot_store.verify_snapshot_integrity(snapshot_id)

        return {
            "snapshot_id": snapshot_id,
            "valid": is_valid,
            "verified_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"Error verifying snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Rollback endpoints
rollback_router = APIRouter(prefix="/api/rollbacks", tags=["rollbacks"])


@rollback_router.post("/plan")
async def plan_rollback(
    rollback_to_action_id: str = Query(...),
    current_action_id: str = Query(...),
) -> dict:
    """Plan a rollback to a checkpoint.

    Args:
        rollback_to_action_id: Action ID to roll back to (checkpoint).
        current_action_id: Current action ID.

    Returns:
        Rollback plan with compensating transactions.
    """
    try:
        rollback_engine = get_rollback_engine()
        plan = rollback_engine.plan_rollback(
            rollback_to_action_id=rollback_to_action_id,
            current_action_id=current_action_id,
        )

        if not plan:
            raise HTTPException(status_code=400, detail="Cannot plan rollback")

        return plan

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error planning rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rollback_router.post("/create")
async def create_rollback(
    rollback_to_action_id: str = Query(...),
    current_action_id: str = Query(...),
    initiated_by: str = Query("system"),
) -> dict:
    """Create and plan a rollback transaction.

    Args:
        rollback_to_action_id: Checkpoint action ID.
        current_action_id: Current action ID.
        initiated_by: User/system initiating rollback.

    Returns:
        Rollback transaction record.
    """
    try:
        rollback_engine = get_rollback_engine()

        # Plan the rollback
        plan = rollback_engine.plan_rollback(
            rollback_to_action_id=rollback_to_action_id,
            current_action_id=current_action_id,
        )

        if not plan:
            raise HTTPException(status_code=400, detail="Cannot plan rollback")

        # Create rollback record
        rollback_id = rollback_engine.create_rollback_record(
            initiated_by=initiated_by,
            rollback_to_action_id=rollback_to_action_id,
            actions_to_rollback=plan["actions_to_rollback"],
            compensating_transactions=plan["compensating_transactions"],
        )

        if not rollback_id:
            raise HTTPException(status_code=400, detail="Failed to create rollback")

        return {
            "rollback_id": rollback_id,
            "status": "pending",
            "plan": plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rollback_router.post("/{rollback_id}/execute")
async def execute_rollback(rollback_id: str) -> dict:
    """Execute a rollback transaction.

    Args:
        rollback_id: Rollback transaction ID.

    Returns:
        Execution result.
    """
    try:
        rollback_engine = get_rollback_engine()
        success = rollback_engine.execute_rollback(rollback_id)

        if not success:
            raise HTTPException(status_code=400, detail="Rollback execution failed")

        status = rollback_engine.get_rollback_status(rollback_id)
        return status

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error executing rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rollback_router.get("/{rollback_id}")
async def get_rollback_status(rollback_id: str) -> dict:
    """Get status of a rollback transaction.

    Args:
        rollback_id: Rollback transaction ID.

    Returns:
        Rollback status.
    """
    try:
        rollback_engine = get_rollback_engine()
        status = rollback_engine.get_rollback_status(rollback_id)

        if not status:
            raise HTTPException(status_code=404, detail="Rollback not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting rollback status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rollback_router.get("/agent/{agent_id}")
async def get_agent_rollback_history(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Get rollback history for an agent.

    Args:
        agent_id: Agent ID.
        limit: Number of records to return.

    Returns:
        List of rollback transactions.
    """
    try:
        rollback_engine = get_rollback_engine()
        history = rollback_engine.get_agent_rollback_history(agent_id, limit)
        return history

    except Exception as e:
        print(f"Error getting rollback history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
