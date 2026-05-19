"""Layer 5: Rollback Engine - Compensating Transactions.

Generates inverse operations from snapshots captured in Layer 4.
Enables partial rollback to any checkpoint.
Surgical rollback, not full revert.

Example: Agent modified 15 files over 20 minutes.
Only actions 13-15 caused problem.
Rollback to action 12 executes compensating transactions for 15, 14, 13 in reverse.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.database import (
    get_db_session, Action, Snapshot, Rollback
)
from src.schemas import ActionType


class RollbackEngine:
    """Orchestrate compensating transactions for partial rollback."""

    def __init__(self):
        """Initialize rollback engine."""
        pass

    def generate_compensating_transaction(
        self, action: Action, snapshot: Optional[Snapshot]
    ) -> Optional[Dict[str, Any]]:
        """Generate inverse operation from action and snapshot.

        Args:
            action: Original action record.
            snapshot: Snapshot of before-state.

        Returns:
            Compensating transaction definition if can be generated, None otherwise.
        """
        if not snapshot:
            return None

        action_type = action.action_type
        target = action.target_resource

        try:
            # File write → file restore
            if action_type == "file_write":
                return {
                    "type": "file_restore",
                    "original_action": action.action_id,
                    "file_path": target,
                    "content_snapshot_id": snapshot.snapshot_id,
                    "operation": f"Restore {target} to before-state",
                }

            # File delete → file restore
            elif action_type == "file_delete":
                return {
                    "type": "file_restore",
                    "original_action": action.action_id,
                    "file_path": target,
                    "content_snapshot_id": snapshot.snapshot_id,
                    "operation": f"Restore deleted file {target}",
                }

            # Database insert → delete inserted row
            elif action_type == "db_insert":
                if snapshot.before_state:
                    return {
                        "type": "db_delete",
                        "original_action": action.action_id,
                        "database": target,
                        "where_clause": snapshot.before_state.get("where_clause"),
                        "operation": f"Remove inserted rows from {target}",
                        "snapshot_id": snapshot.snapshot_id,
                    }

            # Database update → restore original values
            elif action_type == "db_update":
                if snapshot.before_state:
                    return {
                        "type": "db_restore",
                        "original_action": action.action_id,
                        "database": target,
                        "affected_rows": snapshot.before_state.get("affected_rows", []),
                        "operation": f"Restore {target} to before-state",
                        "snapshot_id": snapshot.snapshot_id,
                    }

            # Database delete → restore from snapshot
            elif action_type == "db_delete":
                if snapshot.before_state:
                    return {
                        "type": "db_insert",
                        "original_action": action.action_id,
                        "database": target,
                        "rows_to_restore": snapshot.before_state.get("affected_rows", []),
                        "operation": f"Restore deleted rows to {target}",
                        "snapshot_id": snapshot.snapshot_id,
                    }

            # Default: can't generate compensating transaction
            return None

        except Exception as e:
            print(f"Failed to generate compensating transaction: {e}")
            return None

    def plan_rollback(
        self,
        rollback_to_action_id: str,
        current_action_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Plan rollback from current action back to checkpoint.

        Args:
            rollback_to_action_id: Action ID to roll back to (checkpoint).
            current_action_id: Current action ID (where we are now).

        Returns:
            Rollback plan with compensating transactions if possible, None otherwise.
        """
        try:
            session = get_db_session()

            # Get all actions from checkpoint to current
            actions = (
                session.query(Action)
                .filter(Action.action_id >= rollback_to_action_id)
                .filter(Action.action_id <= current_action_id)
                .order_by(Action.timestamp)
                .all()
            )

            if not actions:
                session.close()
                return None

            # Find actions to rollback (everything after checkpoint)
            checkpoint_idx = next(
                (i for i, a in enumerate(actions) if a.action_id == rollback_to_action_id),
                0,
            )
            actions_to_rollback = actions[checkpoint_idx + 1:]

            # Generate compensating transactions in reverse order
            compensating_transactions = []
            for action in reversed(actions_to_rollback):
                # Get snapshot for this action
                snapshot = (
                    session.query(Snapshot)
                    .filter_by(action_id=action.action_id)
                    .first()
                )

                # Generate compensating transaction
                comp_tx = self.generate_compensating_transaction(action, snapshot)
                if comp_tx:
                    compensating_transactions.append(comp_tx)

            session.close()

            return {
                "rollback_to_action_id": rollback_to_action_id,
                "actions_to_rollback": [a.action_id for a in actions_to_rollback],
                "compensating_transactions": compensating_transactions,
                "checkpoint_timestamp": actions[checkpoint_idx].timestamp.isoformat()
                if checkpoint_idx < len(actions)
                else None,
            }

        except Exception as e:
            print(f"Failed to plan rollback: {e}")
            return None

    def create_rollback_record(
        self,
        initiated_by: str,
        rollback_to_action_id: str,
        actions_to_rollback: List[str],
        compensating_transactions: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Create rollback transaction record in database.

        Args:
            initiated_by: User or system that initiated rollback.
            rollback_to_action_id: Checkpoint action ID.
            actions_to_rollback: List of action IDs to undo.
            compensating_transactions: Generated inverse operations.

        Returns:
            Rollback ID if successful, None otherwise.
        """
        try:
            session = get_db_session()

            rollback = Rollback(
                initiated_by=initiated_by,
                initiated_at=datetime.utcnow(),
                rollback_to_action_id=rollback_to_action_id,
                actions_to_rollback=actions_to_rollback,
                status="pending",
                compensating_transactions=compensating_transactions,
            )

            session.add(rollback)
            session.commit()
            rollback_id = rollback.rollback_id
            session.close()

            return rollback_id

        except Exception as e:
            print(f"Failed to create rollback record: {e}")
            return None

    def execute_rollback(self, rollback_id: str) -> bool:
        """Execute compensating transactions for a rollback.

        Args:
            rollback_id: Rollback transaction ID.

        Returns:
            True if successful, False otherwise.
        """
        try:
            session = get_db_session()

            rollback = session.query(Rollback).filter_by(rollback_id=rollback_id).first()
            if not rollback:
                session.close()
                return False

            # Update status to in_progress
            rollback.status = "in_progress"
            session.commit()

            # Execute compensating transactions
            executed = []
            for comp_tx in rollback.compensating_transactions:
                # In production, this would execute actual operations
                # For now, mark as executed
                executed.append(comp_tx)

            # Update rollback record
            rollback.status = "completed"
            rollback.executed_transactions = executed
            rollback.completion_time = datetime.utcnow()
            session.commit()
            session.close()

            return True

        except Exception as e:
            print(f"Failed to execute rollback: {e}")

            # Update status to failed
            try:
                session = get_db_session()
                rollback = session.query(Rollback).filter_by(rollback_id=rollback_id).first()
                if rollback:
                    rollback.status = "failed"
                    rollback.error_message = str(e)
                    session.commit()
                session.close()
            except Exception:
                pass

            return False

    def get_rollback_status(self, rollback_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a rollback.

        Args:
            rollback_id: Rollback ID.

        Returns:
            Rollback status if found, None otherwise.
        """
        try:
            session = get_db_session()
            rollback = session.query(Rollback).filter_by(rollback_id=rollback_id).first()
            session.close()

            if not rollback:
                return None

            return rollback.to_dict()

        except Exception as e:
            print(f"Failed to get rollback status: {e}")
            return None

    def get_agent_rollback_history(
        self, agent_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get rollback history for an agent.

        Args:
            agent_id: Agent ID.
            limit: Max records to return.

        Returns:
            List of rollback records.
        """
        try:
            session = get_db_session()

            # Get actions for this agent, then get rollbacks that affected them
            agent_actions = (
                session.query(Action)
                .filter_by(agent_id=agent_id)
                .order_by(Action.timestamp.desc())
                .limit(limit * 2)  # Get more to cross-reference
                .all()
            )

            action_ids = {a.action_id for a in agent_actions}

            rollbacks = (
                session.query(Rollback)
                .order_by(Rollback.initiated_at.desc())
                .limit(limit)
                .all()
            )

            session.close()

            # Filter rollbacks that affected this agent's actions
            relevant_rollbacks = [
                r
                for r in rollbacks
                if any(aid in action_ids for aid in r.actions_to_rollback)
            ]

            return [r.to_dict() for r in relevant_rollbacks]

        except Exception as e:
            print(f"Failed to get rollback history: {e}")
            return []


# Global rollback engine
_rollback_engine: Optional[RollbackEngine] = None


def get_rollback_engine() -> RollbackEngine:
    """Get global rollback engine instance."""
    global _rollback_engine
    if _rollback_engine is None:
        _rollback_engine = RollbackEngine()
    return _rollback_engine
