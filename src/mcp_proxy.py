"""MCP Proxy Server - intercepts all tool calls from agents."""

import time
from typing import Any, Optional, Callable
import uuid

from src.classifier import get_classifier
from src.config import get_policy_config
from src.database import get_db_session
from src.policy_engine import get_policy_engine
from src.schemas import (
    ActionContext, ActionType, MCPRequest, MCPResponse, ActionClassification
)


class MCPProxy:
    """MCP proxy that intercepts and controls agent tool calls."""

    def __init__(self):
        """Initialize MCP proxy."""
        self.classifier = get_classifier()
        self.policy_engine = get_policy_engine()
        self.policy_config = get_policy_config()

        # Stats
        self.stats = {
            "total_calls": 0,
            "blocked": 0,
            "flagged": 0,
            "approved": 0,
            "errors": 0,
        }

    def parse_action(self, request: MCPRequest, agent_id: str) -> Optional[ActionContext]:
        """Parse MCP request into ActionContext for classification.

        Args:
            request: Raw MCP request.
            agent_id: ID of the agent making the request.

        Returns:
            ActionContext or None if parsing fails.
        """
        try:
            params = request.params
            method = request.method

            # Extract tool name and arguments
            if method != "tools/call":
                return None

            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            # Map tool to action type
            action_type = self._map_tool_to_action_type(tool_name, arguments)
            if action_type is None:
                return None

            # Extract command and target resource
            command, target_resource = self._extract_command_and_target(
                tool_name, arguments
            )

            # Determine scope from config
            policy_config = get_policy_config()
            agent_policy = policy_config.get_agent_config(agent_id)
            agent_scope = agent_policy.get("scope", "unknown")

            # Check if touches credentials or config
            touches_credentials = self._touches_credentials(command, target_resource)
            touches_config = policy_config.is_config_file(target_resource)

            context = ActionContext(
                action_type=action_type,
                command=command,
                target_resource=target_resource,
                agent_id=agent_id,
                agent_scope=agent_scope,
                touches_credentials=touches_credentials,
                touches_config=touches_config,
            )

            return context

        except Exception as e:
            print(f"Error parsing action: {e}")
            return None

    def _map_tool_to_action_type(
        self, tool_name: str, arguments: dict
    ) -> Optional[ActionType]:
        """Map tool name to ActionType.

        Args:
            tool_name: MCP tool name.
            arguments: Tool arguments.

        Returns:
            ActionType or None if unmappable.
        """
        if tool_name == "bash":
            return ActionType.BASH_RUN

        elif tool_name == "read_file":
            return ActionType.FILE_READ

        elif tool_name == "write_file":
            return ActionType.FILE_WRITE

        elif tool_name == "delete_file":
            return ActionType.FILE_DELETE

        elif tool_name == "list_directory":
            return ActionType.DIR_LIST

        elif tool_name in ["query_db", "execute_sql"]:
            query = arguments.get("query", "").upper()
            if "SELECT" in query:
                return ActionType.DB_SELECT
            elif "INSERT" in query:
                return ActionType.DB_INSERT
            elif "UPDATE" in query:
                return ActionType.DB_UPDATE
            elif "DELETE" in query:
                return ActionType.DB_DELETE
            return ActionType.UNKNOWN

        elif tool_name in ["make_api_call", "http_request"]:
            return ActionType.API_CALL

        elif tool_name == "git":
            return ActionType.GIT_COMMAND

        return ActionType.UNKNOWN

    def _extract_command_and_target(
        self, tool_name: str, arguments: dict
    ) -> tuple[str, str]:
        """Extract command and target resource from arguments.

        Args:
            tool_name: Tool name.
            arguments: Tool arguments.

        Returns:
            Tuple of (command, target_resource).
        """
        if tool_name == "bash":
            command = arguments.get("command", "")
            return command, command.split()[0] if command else ""

        elif tool_name == "read_file":
            path = arguments.get("path", "")
            return f"read {path}", path

        elif tool_name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            return f"write {path} ({len(content)} bytes)", path

        elif tool_name == "delete_file":
            path = arguments.get("path", "")
            return f"delete {path}", path

        elif tool_name == "list_directory":
            path = arguments.get("path", "")
            return f"list {path}", path

        elif tool_name in ["query_db", "execute_sql"]:
            query = arguments.get("query", "")
            return query[:500], arguments.get("database", "unknown")

        else:
            return str(arguments)[:500], ""

    def _touches_credentials(self, command: str, target_resource: str) -> bool:
        """Check if action touches credential files.

        Args:
            command: Command string.
            target_resource: Target resource.

        Returns:
            True if touches credentials.
        """
        credential_patterns = [
            ".env",
            "secret",
            "password",
            "api_key",
            "aws_credentials",
            ".ssh",
            "private_key",
            "token",
        ]

        combined = f"{command} {target_resource}".lower()
        return any(pattern in combined for pattern in credential_patterns)

    def intercept(
        self,
        request: MCPRequest,
        agent_id: str,
        execute_fn: Callable[[MCPRequest], Any],
    ) -> tuple[MCPResponse, str]:
        """Intercept and evaluate an MCP tool call.

        Args:
            request: MCP request.
            agent_id: Agent ID.
            execute_fn: Function to execute the actual tool call.

        Returns:
            Tuple of (response, decision).
            Decision: "approved", "blocked", or "flagged".
        """
        start_time = time.time()
        self.stats["total_calls"] += 1

        # Parse action
        context = self.parse_action(request, agent_id)
        if context is None:
            # Unknown tool, pass through
            result = execute_fn(request)
            return MCPResponse(result=result), "approved"

        # Check additional rules first (can block immediately)
        rule_result = self.policy_engine.check_additional_rules(context)
        if rule_result:
            decision, reason = rule_result
            self.policy_engine.log_action(
                context, None, decision, reason, (time.time() - start_time) * 1000
            )
            self.policy_engine.log_blocked_action(context, reason)

            if decision == "blocked":
                self.stats["blocked"] += 1
                self.policy_engine.create_alert(
                    context, "high", f"Blocked: {reason}"
                )
                error_msg = f"Action blocked by AgentFuse: {reason}"
                return MCPResponse(error=error_msg), "blocked"
            else:
                self.stats["flagged"] += 1

        # Classify
        classification = self.classifier.classify(context)

        # Evaluate
        decision, policy_reason = self.policy_engine.evaluate(context, classification)

        # Capture before-state for yellow/red
        before_state = None
        if classification.classification in [
            ActionClassification.YELLOW,
            ActionClassification.RED,
        ]:
            before_state = self.policy_engine.capture_before_state(context)

        # Log
        action_id = self.policy_engine.log_action(
            context,
            classification,
            decision,
            policy_reason,
            (time.time() - start_time) * 1000,
            before_state=before_state,
        )

        # Execute or block
        if decision == "blocked":
            self.stats["blocked"] += 1
            self.policy_engine.create_alert(
                context, "critical", f"Blocked: {policy_reason}"
            )
            error_msg = f"Action blocked by AgentFuse: {policy_reason}"
            return MCPResponse(error=error_msg), "blocked"

        elif decision == "flagged":
            self.stats["flagged"] += 1
            # Execute but log as flagged
            try:
                result = execute_fn(request)
                after_state = {"status": "executed"}
                # Update with after-state
                self._update_action_after_state(action_id, after_state)
                return MCPResponse(result=result), "flagged"
            except Exception as e:
                self.stats["errors"] += 1
                return MCPResponse(error=str(e)), "flagged"

        else:  # approved
            self.stats["approved"] += 1
            try:
                result = execute_fn(request)
                after_state = {"status": "executed"}
                self._update_action_after_state(action_id, after_state)
                return MCPResponse(result=result), "approved"
            except Exception as e:
                self.stats["errors"] += 1
                return MCPResponse(error=str(e)), "approved"

    def _update_action_after_state(self, action_id: str, after_state: dict) -> None:
        """Update action with after-state.

        Args:
            action_id: Action ID.
            after_state: After-state data.
        """
        try:
            session = get_db_session()
            from src.database import Action
            action = session.query(Action).filter_by(action_id=action_id).first()
            if action:
                action.after_state = after_state
                session.commit()
            session.close()
        except Exception as e:
            print(f"Failed to update action after-state: {e}")

    def get_stats(self) -> dict:
        """Get proxy statistics.

        Returns:
            Statistics dictionary.
        """
        total = self.stats["total_calls"]
        return {
            "total_calls": total,
            "approved": self.stats["approved"],
            "flagged": self.stats["flagged"],
            "blocked": self.stats["blocked"],
            "errors": self.stats["errors"],
            "block_rate": (
                self.stats["blocked"] / total if total > 0 else 0
            ),
        }


# Global proxy instance
_proxy: Optional[MCPProxy] = None


def get_proxy() -> MCPProxy:
    """Get global MCP proxy instance."""
    global _proxy
    if _proxy is None:
        _proxy = MCPProxy()
    return _proxy
