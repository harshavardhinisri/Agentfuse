"""Policy engine for enforcing action controls based on classification.

Defense in Depth Strategy:
1. Layer 3: Deterministic scope rules (hard backstop)
2. Layer 2: ML classifier (probabilistic judgment)
3. Policies: Decision rules based on classification
"""

import time
from datetime import datetime
from typing import Optional

from src.config import get_policy_config
from src.database import (
    get_db_session, Action, AlertLog, BlockedAction, AgentPolicy
)
from src.schemas import (
    ActionClassification, ActionContext, ClassificationResult, ActionLog
)
from src.layers import get_scope_rule_engine


class PolicyEngine:
    """Enforce policies based on action classification."""

    DECISION_APPROVED = "approved"
    DECISION_BLOCKED = "blocked"
    DECISION_FLAGGED = "flagged"

    def __init__(self):
        """Initialize policy engine."""
        self.policy_config = get_policy_config()

    def _get_agent_policy(self, agent_id: str) -> dict:
        """Get policy for a specific agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Agent policy configuration.
        """
        try:
            session = get_db_session()
            policy = session.query(AgentPolicy).filter_by(agent_id=agent_id).first()
            session.close()

            if policy:
                return {
                    "agent_id": policy.agent_id,
                    "scope": policy.scope,
                    "max_parallel_actions": policy.max_parallel_actions,
                    "require_approval_on_yellow": policy.require_approval_on_yellow,
                    "require_approval_on_red": policy.require_approval_on_red,
                    "auto_rollback_on_error": policy.auto_rollback_on_error,
                }
        except Exception as e:
            print(f"Failed to load agent policy: {e}")

        # Fall back to config file
        return self.policy_config.get_agent_config(agent_id)

    def evaluate(
        self,
        context: ActionContext,
        classification: ClassificationResult,
    ) -> tuple[str, Optional[str]]:
        """Evaluate if an action should be approved or blocked.

        Defense in depth strategy:
        1. Layer 3: Check deterministic scope rules (hard backstop)
        2. Layer 2: Use ML classification
        3. Apply policy decisions

        Args:
            context: Action context.
            classification: Classification result from DeBERTa.

        Returns:
            Tuple of (decision, reason).
            Decision: "approved", "blocked", or "flagged".
            Reason: Human-readable explanation.
        """
        agent_policy = self._get_agent_policy(context.agent_id)
        scope = agent_policy.get("scope", context.agent_scope)

        # Update context with determined scope
        context.is_prod = self.policy_config.is_prod_scope(scope)

        reasons = []

        # LAYER 3: Check deterministic scope rules FIRST (before classifier)
        # These are absolute backstops - cannot be overridden
        scope_engine = get_scope_rule_engine()
        scope_result = scope_engine.evaluate_scope_rules(context)
        if scope_result:
            decision, reason = scope_result
            if decision == "blocked":
                return (self.DECISION_BLOCKED, reason)

        # Rule 1: Red actions are blocked by default
        if classification.classification == ActionClassification.RED:
            reasons.append(f"RED classification ({classification.confidence:.0%} confidence)")

            # Check if red actions are allowed for this agent
            if not agent_policy.get("require_approval_on_red", True):
                reasons.append("Agent policy allows RED without approval")
                return self.DECISION_APPROVED, " | ".join(reasons)

            return self.DECISION_BLOCKED, " | ".join(reasons)

        # Rule 2: Yellow actions proceed but are flagged
        if classification.classification == ActionClassification.YELLOW:
            reasons.append(f"YELLOW classification ({classification.confidence:.0%} confidence)")

            if agent_policy.get("require_approval_on_yellow", False):
                reasons.append("Agent policy requires approval on YELLOW")
                return self.DECISION_BLOCKED, " | ".join(reasons)

            return self.DECISION_FLAGGED, " | ".join(reasons)

        # Rule 3: Green actions are auto-approved
        if classification.classification == ActionClassification.GREEN:
            reasons.append(f"GREEN classification ({classification.confidence:.0%} confidence)")
            return self.DECISION_APPROVED, " | ".join(reasons)

        # Default: flag unknown classifications
        reasons.append("Unknown classification")
        return self.DECISION_FLAGGED, " | ".join(reasons)

    def check_additional_rules(
        self,
        context: ActionContext,
    ) -> Optional[tuple[str, str]]:
        """Check additional policy rules that might block/flag an action.

        Args:
            context: Action context.

        Returns:
            Tuple of (decision, reason) if a rule is triggered, None otherwise.
        """
        # Rule: Config file access
        if self.policy_config.is_config_file(context.target_resource):
            if context.is_prod:
                return self.DECISION_BLOCKED, "Production config file access"
            else:
                return self.DECISION_FLAGGED, "Config file access (flagged for review)"

        # Rule: Dangerous bash commands
        if self.policy_config.is_dangerous_command(context.command):
            return self.DECISION_BLOCKED, "Dangerous bash pattern detected"

        return None

    def log_action(
        self,
        context: ActionContext,
        classification: ClassificationResult,
        decision: str,
        reason: Optional[str] = None,
        duration_ms: float = 0.0,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
    ) -> str:
        """Log action to database.

        Args:
            context: Action context.
            classification: Classification result.
            decision: Action decision (approved/blocked/flagged).
            reason: Human-readable reason.
            duration_ms: Execution duration in milliseconds.
            before_state: Before-state snapshot.
            after_state: Execution result.

        Returns:
            Action ID.
        """
        try:
            session = get_db_session()

            action = Action(
                agent_id=context.agent_id,
                action_type=context.action_type.value,
                command=context.command,
                target_resource=context.target_resource,
                classification=classification.classification.value,
                confidence=classification.confidence,
                decision=decision,
                reason=reason,
                before_state=before_state,
                after_state=after_state,
                timestamp=context.timestamp,
                duration_ms=duration_ms,
            )

            session.add(action)
            session.commit()
            action_id = action.action_id
            session.close()

            return action_id

        except Exception as e:
            print(f"Failed to log action: {e}")
            # Return a dummy ID so execution can continue
            return f"error-{int(time.time())}"

    def log_blocked_action(
        self,
        context: ActionContext,
        reason: str,
    ) -> str:
        """Log a blocked action for potential review/replay.

        Args:
            context: Action context.
            reason: Reason for blocking.

        Returns:
            Blocked action ID.
        """
        try:
            session = get_db_session()

            blocked = BlockedAction(
                agent_id=context.agent_id,
                command=context.command,
                target_resource=context.target_resource,
                reason=reason,
                blocked_at=context.timestamp,
            )

            session.add(blocked)
            session.commit()
            action_id = blocked.action_id
            session.close()

            return action_id

        except Exception as e:
            print(f"Failed to log blocked action: {e}")
            return "error"

    def create_alert(
        self,
        context: ActionContext,
        severity: str,
        message: str,
    ) -> str:
        """Create alert for dangerous actions.

        Args:
            context: Action context.
            severity: Alert severity (critical/high/medium).
            message: Alert message.

        Returns:
            Alert ID.
        """
        try:
            session = get_db_session()

            alert = AlertLog(
                action_id=f"blocked-{int(time.time())}",
                agent_id=context.agent_id,
                action_type=context.action_type.value,
                command=context.command[:2000],
                severity=severity,
                message=message,
                created_at=context.timestamp,
            )

            session.add(alert)
            session.commit()
            alert_id = alert.alert_id
            session.close()

            return alert_id

        except Exception as e:
            print(f"Failed to create alert: {e}")
            return "error"

    def capture_before_state(
        self,
        context: ActionContext,
    ) -> Optional[dict]:
        """Capture system state before action execution.

        Args:
            context: Action context.

        Returns:
            Before-state snapshot.
        """
        # For now, return basic metadata
        # Day 4 will implement actual before-state snapshots
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": context.agent_id,
            "action_type": context.action_type.value,
            "target_resource": context.target_resource,
        }


# Global policy engine instance
_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get global policy engine instance."""
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine
