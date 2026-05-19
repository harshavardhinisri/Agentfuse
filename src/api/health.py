"""Health check endpoints."""

import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.classifier import get_classifier
from src.database import get_db_manager
from src.mcp_proxy import get_proxy
from src.schemas import HealthResponse, StatsResponse


router = APIRouter(prefix="/api", tags=["health"])

# Server start time
_start_time = time.time()


@router.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        Health status with model and database status.
    """
    # Check classifier
    classifier = get_classifier()
    classifier_ok = classifier.health_check()

    # Check database
    db_manager = get_db_manager()
    db_ok = db_manager.health_check()

    # Determine overall status
    if classifier_ok and db_ok:
        status = "healthy"
    elif classifier_ok or db_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    # Get classifier latency
    classifier_latency = 0.0
    if classifier_ok:
        start = time.time()
        classifier.classify(None)
        classifier_latency = (time.time() - start) * 1000

    uptime = time.time() - _start_time

    return HealthResponse(
        status=status,
        model_loaded=classifier_ok,
        db_connected=db_ok,
        classifier_latency_ms=classifier_latency,
        uptime_seconds=uptime,
    )


@router.get("/stats")
async def get_stats() -> StatsResponse:
    """Get action statistics.

    Returns:
        Action statistics for today.
    """
    try:
        from src.database import get_db_session, Action
        from sqlalchemy import func
        from datetime import datetime, timedelta

        session = get_db_session()

        # Get all-time counts
        total_actions = session.query(func.count(Action.action_id)).scalar() or 0
        green_count = (
            session.query(func.count(Action.action_id))
            .filter_by(classification="green")
            .scalar() or 0
        )
        yellow_count = (
            session.query(func.count(Action.action_id))
            .filter_by(classification="yellow")
            .scalar() or 0
        )
        red_count = (
            session.query(func.count(Action.action_id))
            .filter_by(classification="red")
            .scalar() or 0
        )
        blocked_count = (
            session.query(func.count(Action.action_id))
            .filter_by(decision="blocked")
            .scalar() or 0
        )

        # Get today's count
        today = datetime.utcnow().date()
        actions_today = (
            session.query(func.count(Action.action_id))
            .filter(func.date(Action.timestamp) == today)
            .scalar() or 0
        )

        # Get average classification time
        avg_duration = (
            session.query(func.avg(Action.duration_ms))
            .scalar() or 0.0
        )

        session.close()

        return StatsResponse(
            total_actions_logged=total_actions,
            green_count=green_count,
            yellow_count=yellow_count,
            red_count=red_count,
            blocked_actions=blocked_count,
            actions_today=actions_today,
            avg_classification_time_ms=float(avg_duration),
        )

    except Exception as e:
        print(f"Error getting stats: {e}")
        return StatsResponse(
            total_actions_logged=0,
            green_count=0,
            yellow_count=0,
            red_count=0,
            blocked_actions=0,
            actions_today=0,
            avg_classification_time_ms=0.0,
        )


@router.get("/proxy/stats")
async def get_proxy_stats() -> dict:
    """Get MCP proxy statistics.

    Returns:
        Proxy call statistics.
    """
    proxy = get_proxy()
    return proxy.get_stats()
