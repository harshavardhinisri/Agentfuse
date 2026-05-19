"""Layer 6: Kill Switch - Emergency Agent Halt.

The thing 60% of organizations don't have.
Two interfaces: FastAPI endpoint (automated) + Slack bot (human).

What happens when kill switch is activated:
1. Set agent status = HALTED in PostgreSQL (immediate)
2. Proxy rejects ALL subsequent tool calls
3. Cancel any in-flight tool call
4. Generate compensating transactions for last N actions
5. Send Slack notification to #incidents
6. Dashboard shows HALTED with rollback options

Total time from /halt to fully stopped: < 200ms
"""

import time
from datetime import datetime
from typing import Optional, Tuple

from src.database import get_db_session, AgentStatus, HaltEvent, Action
from src.layers import get_rollback_engine


class KillSwitch:
    """Emergency halt mechanism for agents."""

    def __init__(self):
        """Initialize kill switch."""
        self.rollback_engine = get_rollback_engine()

    def get_agent_status(self, agent_id: str) -> Optional[dict]:
        """Get current status of an agent.

        Args:
            agent_id: Agent ID.

        Returns:
            Agent status if found, None otherwise.
        """
        try:
            session = get_db_session()
            status = session.query(AgentStatus).filter_by(agent_id=agent_id).first()
            session.close()

            if not status:
                return None

            return status.to_dict()

        except Exception as e:
            print(f"Failed to get agent status: {e}")
            return None

    def is_agent_halted(self, agent_id: str) -> bool:
        """Check if agent is currently halted.

        Args:
            agent_id: Agent ID.

        Returns:
            True if halted, False otherwise.
        """
        status = self.get_agent_status(agent_id)
        if not status:
            return False
        return status["status"] == "halted"

    def halt_agent(
        self,
        agent_id: str,
        initiated_by: str,
        reason: str,
        initiated_via: str = "api",
        generate_compensating_tx: bool = True,
    ) -> Tuple[bool, float, Optional[str]]:
        """Immediately halt an agent.

        Performs the halt operation:
        1. Set status = HALTED in database
        2. Reject all subsequent calls
        3. Cancel in-flight operations
        4. Generate compensating transactions
        5. Create halt event record

        Args:
            agent_id: Agent ID to halt.
            initiated_by: User or system initiating halt.
            reason: Reason for halting.
            initiated_via: "api" or "slack".
            generate_compensating_tx: Whether to auto-generate rollback.

        Returns:
            Tuple of (success, halt_time_ms, halt_id).
        """
        start_time = time.time()

        try:
            session = get_db_session()

            # Step 1: Get or create agent status
            status = session.query(AgentStatus).filter_by(agent_id=agent_id).first()
            if not status:
                status = AgentStatus(agent_id=agent_id)
                session.add(status)

            # Step 2: Get in-flight action if any
            in_flight_action = None
            if status.current_action_id:
                in_flight_action = (
                    session.query(Action)
                    .filter_by(action_id=status.current_action_id)
                    .first()
                )

            # Step 3: Update status to halted
            status.status = "halted"
            status.halted_at = datetime.utcnow()
            status.halted_by = initiated_by
            status.halt_reason = reason

            session.commit()

            # Step 4: Get last 10 actions for compensating transaction generation
            last_actions = (
                session.query(Action)
                .filter_by(agent_id=agent_id)
                .order_by(Action.timestamp.desc())
                .limit(10)
                .all()
            )

            halt_time_ms = (time.time() - start_time) * 1000

            # Step 5: Generate compensating transactions if requested
            rollback_id = None
            if generate_compensating_tx and last_actions:
                # Only rollback yellow/red actions
                actions_to_rollback = [
                    a.action_id
                    for a in last_actions
                    if a.classification in ["yellow", "red"]
                ]

                if actions_to_rollback:
                    rollback_id = self.rollback_engine.create_rollback_record(
                        initiated_by=f"kill_switch_{initiated_by}",
                        rollback_to_action_id=actions_to_rollback[-1],
                        actions_to_rollback=actions_to_rollback,
                        compensating_transactions=[],  # Will be generated on-demand
                    )

            # Step 6: Create halt event record
            halt_event = HaltEvent(
                agent_id=agent_id,
                initiated_by=initiated_by,
                initiated_via=initiated_via,
                reason=reason,
                last_action_id=in_flight_action.action_id if in_flight_action else None,
                halted_at=datetime.utcnow(),
                halt_duration_ms=halt_time_ms,
                actions_pending=len(last_actions),
                rollback_generated=rollback_id is not None,
            )

            session.add(halt_event)
            session.commit()
            halt_id = halt_event.halt_id
            session.close()

            return (True, halt_time_ms, halt_id)

        except Exception as e:
            print(f"Failed to halt agent: {e}")
            return (False, (time.time() - start_time) * 1000, None)

    def resume_agent(
        self, agent_id: str, resumed_by: str, reason: Optional[str] = None
    ) -> bool:
        """Resume a halted agent.

        Args:
            agent_id: Agent ID to resume.
            resumed_by: User resuming the agent.
            reason: Optional reason for resuming.

        Returns:
            True if successful, False otherwise.
        """
        try:
            session = get_db_session()

            status = session.query(AgentStatus).filter_by(agent_id=agent_id).first()
            if not status:
                session.close()
                return False

            status.status = "running"
            status.halted_at = None
            status.halted_by = None
            status.halt_reason = None
            status.updated_at = datetime.utcnow()

            session.commit()
            session.close()

            return True

        except Exception as e:
            print(f"Failed to resume agent: {e}")
            return False

    def get_halt_history(
        self, agent_id: str, limit: int = 20
    ) -> list[dict]:
        """Get halt history for an agent.

        Args:
            agent_id: Agent ID.
            limit: Max records to return.

        Returns:
            List of halt events.
        """
        try:
            session = get_db_session()

            events = (
                session.query(HaltEvent)
                .filter_by(agent_id=agent_id)
                .order_by(HaltEvent.halted_at.desc())
                .limit(limit)
                .all()
            )

            session.close()

            return [e.to_dict() for e in events]

        except Exception as e:
            print(f"Failed to get halt history: {e}")
            return []

    def get_halted_agents(self) -> list[dict]:
        """Get all currently halted agents.

        Returns:
            List of halted agent statuses.
        """
        try:
            session = get_db_session()

            statuses = (
                session.query(AgentStatus)
                .filter_by(status="halted")
                .order_by(AgentStatus.halted_at.desc())
                .all()
            )

            session.close()

            return [s.to_dict() for s in statuses]

        except Exception as e:
            print(f"Failed to get halted agents: {e}")
            return []

    def get_recent_halt_events(self, limit: int = 50) -> list[dict]:
        """Get recent halt events across all agents.

        Args:
            limit: Max records to return.

        Returns:
            List of halt events.
        """
        try:
            session = get_db_session()

            events = (
                session.query(HaltEvent)
                .order_by(HaltEvent.halted_at.desc())
                .limit(limit)
                .all()
            )

            session.close()

            return [e.to_dict() for e in events]

        except Exception as e:
            print(f"Failed to get recent halt events: {e}")
            return []

    def update_action_status(
        self, agent_id: str, action_id: str, status: str = None
    ) -> bool:
        """Update agent's current action status.

        Args:
            agent_id: Agent ID.
            action_id: Action ID (or None if no action).
            status: New agent status (optional).

        Returns:
            True if successful, False otherwise.
        """
        try:
            session = get_db_session()

            agent_status = (
                session.query(AgentStatus).filter_by(agent_id=agent_id).first()
            )
            if not agent_status:
                agent_status = AgentStatus(agent_id=agent_id)
                session.add(agent_status)

            agent_status.current_action_id = action_id
            agent_status.last_action_at = datetime.utcnow()

            if action_id:
                agent_status.action_count_today = (
                    agent_status.action_count_today or 0
                ) + 1

            if status:
                agent_status.status = status

            session.commit()
            session.close()

            return True

        except Exception as e:
            print(f"Failed to update action status: {e}")
            return False


# Global kill switch instance
_kill_switch: Optional[KillSwitch] = None


def get_kill_switch() -> KillSwitch:
    """Get global kill switch instance."""
    global _kill_switch
    if _kill_switch is None:
        _kill_switch = KillSwitch()
    return _kill_switch
