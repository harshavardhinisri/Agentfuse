"""Slack bot for AgentFuse - Kill switch via Slack commands.

Slack command: /agentfuse halt <agent-id> [reason]
Slack command: /agentfuse status <agent-id>
Slack command: /agentfuse resume <agent-id>

Sends notifications to #incidents channel on halt events.
"""

import json
import os
from typing import Optional, Dict, Any

from src.layers import get_kill_switch
from src.config import get_settings


class SlackBot:
    """Slack integration for AgentFuse kill switch."""

    def __init__(self, slack_webhook_url: Optional[str] = None):
        """Initialize Slack bot.

        Args:
            slack_webhook_url: Slack webhook URL for notifications.
        """
        self.slack_webhook_url = slack_webhook_url or os.getenv(
            "AGENTFUSE_SLACK_WEBHOOK_URL"
        )
        self.incidents_channel = os.getenv(
            "AGENTFUSE_INCIDENTS_CHANNEL", "#incidents"
        )
        self.kill_switch = get_kill_switch()

    def handle_slash_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Slack slash command.

        Args:
            payload: Slack command payload.

        Returns:
            Response for Slack.
        """
        try:
            command_text = payload.get("text", "").strip()
            user_id = payload.get("user_id", "unknown")
            user_name = payload.get("user_name", user_id)

            # Parse command: /agentfuse halt <agent-id> [reason]
            parts = command_text.split(maxsplit=2)
            action = parts[0] if parts else ""
            agent_id = parts[1] if len(parts) > 1 else ""
            reason = parts[2] if len(parts) > 2 else f"Halted by {user_name}"

            if action == "halt":
                return self._handle_halt(user_name, agent_id, reason)
            elif action == "status":
                return self._handle_status(agent_id)
            elif action == "resume":
                return self._handle_resume(user_name, agent_id)
            else:
                return self._format_help_message()

        except Exception as e:
            print(f"Error handling slash command: {e}")
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error: {str(e)}",
            }

    def _handle_halt(self, user_name: str, agent_id: str, reason: str) -> Dict[str, str]:
        """Handle halt command.

        Args:
            user_name: Slack user name.
            agent_id: Agent to halt.
            reason: Reason for halt.

        Returns:
            Slack response.
        """
        if not agent_id:
            return {
                "response_type": "ephemeral",
                "text": "❌ Usage: `/agentfuse halt <agent-id> [reason]`",
            }

        # Execute halt
        success, halt_time_ms, halt_id = self.kill_switch.halt_agent(
            agent_id=agent_id,
            initiated_by=user_name,
            reason=reason,
            initiated_via="slack",
        )

        if success:
            # Send notification to incidents channel
            self._notify_halt(agent_id, user_name, reason, halt_time_ms, halt_id)

            return {
                "response_type": "in_channel",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🛑 *Agent Halted*\n"
                            f"Agent: `{agent_id}`\n"
                            f"By: {user_name}\n"
                            f"Reason: {reason}\n"
                            f"Halt Time: {halt_time_ms:.1f}ms",
                        },
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Resume Agent"},
                                "value": agent_id,
                                "action_id": "resume_agent",
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "View Dashboard"},
                                "url": f"https://agentfuse.internal/agents/{agent_id}",
                            },
                        ],
                    },
                ],
            }
        else:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Failed to halt agent {agent_id}",
            }

    def _handle_status(self, agent_id: str) -> Dict[str, Any]:
        """Handle status command.

        Args:
            agent_id: Agent to check.

        Returns:
            Slack response.
        """
        if not agent_id:
            return {
                "response_type": "ephemeral",
                "text": "❌ Usage: `/agentfuse status <agent-id>`",
            }

        status = self.kill_switch.get_agent_status(agent_id)

        if not status:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Agent `{agent_id}` not found",
            }

        status_emoji = (
            "🛑" if status["status"] == "halted" else "✅"
        )
        halted_info = (
            f"\nHalted by: {status['halted_by']}\n"
            f"Reason: {status['halt_reason']}"
            if status["status"] == "halted"
            else ""
        )

        return {
            "response_type": "ephemeral",
            "text": f"{status_emoji} *Agent Status*\n"
            f"Agent: `{agent_id}`\n"
            f"Status: {status['status'].upper()}{halted_info}\n"
            f"Actions Today: {status['action_count_today']}\n"
            f"Errors: {status['error_count']}",
        }

    def _handle_resume(self, user_name: str, agent_id: str) -> Dict[str, str]:
        """Handle resume command.

        Args:
            user_name: Slack user name.
            agent_id: Agent to resume.

        Returns:
            Slack response.
        """
        if not agent_id:
            return {
                "response_type": "ephemeral",
                "text": "❌ Usage: `/agentfuse resume <agent-id>`",
            }

        success = self.kill_switch.resume_agent(
            agent_id=agent_id, resumed_by=user_name, reason="Resumed via Slack"
        )

        if success:
            return {
                "response_type": "in_channel",
                "text": f"✅ Agent `{agent_id}` resumed by {user_name}",
            }
        else:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Failed to resume agent {agent_id}",
            }

    def _format_help_message(self) -> Dict[str, str]:
        """Format help message.

        Returns:
            Help message.
        """
        return {
            "response_type": "ephemeral",
            "text": "AgentFuse Kill Switch Commands:\n"
            "`/agentfuse halt <agent-id> [reason]` - Halt an agent immediately\n"
            "`/agentfuse status <agent-id>` - Check agent status\n"
            "`/agentfuse resume <agent-id>` - Resume a halted agent\n"
            "`/agentfuse help` - Show this help message",
        }

    def _notify_halt(
        self, agent_id: str, initiated_by: str, reason: str, halt_time_ms: float, halt_id: str
    ) -> None:
        """Send Slack notification for halt event.

        Args:
            agent_id: Agent that was halted.
            initiated_by: User who initiated halt.
            reason: Reason for halt.
            halt_time_ms: Time to halt in milliseconds.
            halt_id: Halt event ID.
        """
        if not self.slack_webhook_url:
            return

        try:
            import requests

            message = {
                "channel": self.incidents_channel,
                "username": "AgentFuse Kill Switch",
                "icon_emoji": ":stop_button:",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🛑 Agent Halted - Kill Switch Activated",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Agent ID*\n`{agent_id}`",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Initiated By*\n{initiated_by}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Reason*\n{reason}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Halt Time*\n{halt_time_ms:.1f}ms",
                            },
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Halt ID: `{halt_id}`",
                            },
                        ],
                    },
                ],
            }

            requests.post(self.slack_webhook_url, json=message, timeout=5)

        except Exception as e:
            print(f"Failed to send Slack notification: {e}")

    def notify_halt_event(
        self,
        agent_id: str,
        initiated_by: str,
        reason: str,
        halt_time_ms: float,
        halt_id: str,
    ) -> None:
        """Notify about a halt event via Slack.

        Args:
            agent_id: Agent that was halted.
            initiated_by: User who initiated halt.
            reason: Reason for halt.
            halt_time_ms: Time to halt in milliseconds.
            halt_id: Halt event ID.
        """
        self._notify_halt(agent_id, initiated_by, reason, halt_time_ms, halt_id)


# Global Slack bot instance
_slack_bot: Optional[SlackBot] = None


def get_slack_bot() -> SlackBot:
    """Get global Slack bot instance."""
    global _slack_bot
    if _slack_bot is None:
        _slack_bot = SlackBot()
    return _slack_bot
