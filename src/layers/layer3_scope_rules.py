"""Layer 3: Policy Engine with Deterministic Scope Rules.

Acts as a deterministic safety net BEFORE the ML classifier.
If scope rules block something, it's blocked regardless of classifier confidence.
Defense in depth: classifier handles probabilistic judgment,
scope rules are absolute backstop for things that must never happen.
"""

import re
from typing import Optional, Tuple

from src.database import get_db_session, ScopeRule
from src.schemas import ActionContext, ActionType


class ScopeRuleEngine:
    """Deterministic scope rules for agents (Layer 3)."""

    RULE_TYPES = {
        "allowed_paths": "Whitelist of allowed file paths",
        "blocked_paths": "Blacklist of forbidden file paths",
        "allowed_db_prefixes": "Allowed database name patterns",
        "blocked_db_ops": "Blocked database operations (DROP, TRUNCATE, DELETE)",
        "blocked_shell": "Blocked shell commands (rm -rf, chmod 777, etc)",
        "max_files_per_action": "Max files in single operation",
        "require_approval": "Actions requiring manual approval",
    }

    def __init__(self):
        """Initialize scope rule engine."""
        self.rules_cache = {}  # Cache agent rules

    def _load_agent_rules(self, agent_id: str) -> dict:
        """Load all rules for an agent from database.

        Args:
            agent_id: Agent ID.

        Returns:
            Dictionary of rules by type.
        """
        if agent_id in self.rules_cache:
            return self.rules_cache[agent_id]

        try:
            session = get_db_session()
            rules = (
                session.query(ScopeRule)
                .filter_by(agent_id=agent_id, enabled=True)
                .all()
            )
            session.close()

            rules_dict = {}
            for rule in rules:
                rule_type = rule.rule_type
                if rule_type not in rules_dict:
                    rules_dict[rule_type] = []
                rules_dict[rule_type].append(rule.pattern)

            self.rules_cache[agent_id] = rules_dict
            return rules_dict

        except Exception as e:
            print(f"Failed to load agent rules: {e}")
            return {}

    def check_path_access(
        self, context: ActionContext
    ) -> Optional[Tuple[str, str]]:
        """Check if path access is allowed.

        Args:
            context: Action context.

        Returns:
            Tuple of (decision, reason) if blocked, None otherwise.
        """
        if context.action_type not in [
            ActionType.FILE_READ,
            ActionType.FILE_WRITE,
            ActionType.FILE_DELETE,
            ActionType.DIR_LIST,
        ]:
            return None

        rules = self._load_agent_rules(context.agent_id)
        target = context.target_resource

        # Check blocked paths first
        blocked_paths = rules.get("blocked_paths", [])
        for blocked_pattern in blocked_paths:
            if self._match_pattern(target, blocked_pattern):
                return ("blocked", f"Path blocked by rule: {blocked_pattern}")

        # Check allowed paths if defined
        allowed_paths = rules.get("allowed_paths", [])
        if allowed_paths:
            allowed = any(
                self._match_pattern(target, pattern) for pattern in allowed_paths
            )
            if not allowed:
                return ("blocked", "Path not in allowed list")

        return None

    def check_database_access(
        self, context: ActionContext
    ) -> Optional[Tuple[str, str]]:
        """Check if database operation is allowed.

        Args:
            context: Action context.

        Returns:
            Tuple of (decision, reason) if blocked, None otherwise.
        """
        if context.action_type not in [
            ActionType.DB_SELECT,
            ActionType.DB_INSERT,
            ActionType.DB_UPDATE,
            ActionType.DB_DELETE,
        ]:
            return None

        rules = self._load_agent_rules(context.agent_id)
        target = context.target_resource  # Database name
        command = context.command.upper()

        # Check blocked database operations
        blocked_ops = rules.get("blocked_db_ops", [])
        for blocked_pattern in blocked_ops:
            if blocked_pattern.upper() in command:
                return ("blocked", f"Database operation blocked: {blocked_pattern}")

        # Check allowed database prefixes
        allowed_prefixes = rules.get("allowed_db_prefixes", [])
        if allowed_prefixes:
            allowed = any(
                target.startswith(prefix) for prefix in allowed_prefixes
            )
            if not allowed:
                return ("blocked", "Database not in allowed list")

        return None

    def check_shell_command(
        self, context: ActionContext
    ) -> Optional[Tuple[str, str]]:
        """Check if shell command is allowed.

        Args:
            context: Action context.

        Returns:
            Tuple of (decision, reason) if blocked, None otherwise.
        """
        if context.action_type != ActionType.BASH_RUN:
            return None

        rules = self._load_agent_rules(context.agent_id)
        command = context.command

        # Check blocked shell patterns
        blocked_patterns = rules.get("blocked_shell", [])
        for pattern in blocked_patterns:
            if pattern.lower() in command.lower():
                return ("blocked", f"Shell command blocked: {pattern}")

        return None

    def check_resource_limits(
        self, context: ActionContext
    ) -> Optional[Tuple[str, str]]:
        """Check resource limits for action.

        Args:
            context: Action context.

        Returns:
            Tuple of (decision, reason) if blocked, None otherwise.
        """
        rules = self._load_agent_rules(context.agent_id)

        # Check max files per action (for bulk operations)
        max_files = rules.get("max_files_per_action", [None])[0] if rules.get("max_files_per_action") else None
        if max_files and isinstance(max_files, int):
            # This would be checked against actual file count in operation
            pass

        return None

    def require_approval(self, context: ActionContext) -> bool:
        """Check if action requires approval.

        Args:
            context: Action context.

        Returns:
            True if approval required, False otherwise.
        """
        rules = self._load_agent_rules(context.agent_id)
        required_approval = rules.get("require_approval", [])

        for approval_pattern in required_approval:
            if approval_pattern in context.command:
                return True

        return False

    def _match_pattern(self, target: str, pattern: str) -> bool:
        """Match target against pattern (supports wildcards and regex).

        Args:
            target: Target string (path, database name, etc).
            pattern: Pattern (supports * wildcards and /regex/).

        Returns:
            True if match, False otherwise.
        """
        # Check if pattern is regex (enclosed in /)
        if pattern.startswith("/") and pattern.endswith("/"):
            regex_pattern = pattern[1:-1]
            try:
                return bool(re.search(regex_pattern, target))
            except re.error:
                return False

        # Wildcard matching
        if "*" in pattern:
            regex_pattern = pattern.replace("*", ".*").replace(".", r"\.")
            try:
                return bool(re.match(regex_pattern, target))
            except re.error:
                return False

        # Exact match
        return target == pattern

    def evaluate_scope_rules(
        self, context: ActionContext
    ) -> Optional[Tuple[str, str]]:
        """Evaluate all scope rules for action.

        Acts as deterministic safety net BEFORE classifier.
        Returns immediately if any rule blocks.

        Args:
            context: Action context.

        Returns:
            Tuple of (decision, reason) if blocked, None otherwise.
        """
        # Check rules in order of importance
        checks = [
            ("path", self.check_path_access),
            ("database", self.check_database_access),
            ("shell", self.check_shell_command),
            ("resource", self.check_resource_limits),
        ]

        for check_name, check_fn in checks:
            result = check_fn(context)
            if result:
                decision, reason = result
                if decision == "blocked":
                    return (decision, f"[Scope Rule - {check_name}] {reason}")

        return None

    def add_rule(
        self,
        agent_id: str,
        rule_type: str,
        pattern: str,
        operation: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Add a scope rule for an agent.

        Args:
            agent_id: Agent ID.
            rule_type: Type of rule.
            pattern: Pattern to match.
            operation: Optional specific operation.
            description: Optional description.

        Returns:
            True if added successfully, False otherwise.
        """
        try:
            session = get_db_session()

            rule = ScopeRule(
                agent_id=agent_id,
                rule_type=rule_type,
                pattern=pattern,
                operation=operation,
                description=description,
                enabled=True,
            )

            session.add(rule)
            session.commit()
            session.close()

            # Invalidate cache
            if agent_id in self.rules_cache:
                del self.rules_cache[agent_id]

            return True

        except Exception as e:
            print(f"Failed to add scope rule: {e}")
            return False

    def reload_rules(self, agent_id: str) -> None:
        """Reload rules for an agent.

        Args:
            agent_id: Agent ID.
        """
        if agent_id in self.rules_cache:
            del self.rules_cache[agent_id]


# Global scope rule engine
_scope_engine: Optional[ScopeRuleEngine] = None


def get_scope_rule_engine() -> ScopeRuleEngine:
    """Get global scope rule engine instance."""
    global _scope_engine
    if _scope_engine is None:
        _scope_engine = ScopeRuleEngine()
    return _scope_engine
