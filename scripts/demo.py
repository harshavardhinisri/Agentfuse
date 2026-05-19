"""Demo: Run AgentFuse and show it blocking dangerous actions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schemas import ActionContext, ActionType, MCPRequest
from src.mcp_proxy import get_proxy
from src.classifier import get_classifier


def demo_action(
    name: str,
    action_type: ActionType,
    command: str,
    target_resource: str,
    agent_id: str,
    agent_scope: str,
):
    """Run a demo action through the proxy.

    Args:
        name: Demo name.
        action_type: Type of action.
        command: Command string.
        target_resource: Target resource.
        agent_id: Agent ID.
        agent_scope: Agent scope.
    """
    print(f"\n{'='*70}")
    print(f"📋 {name}")
    print(f"{'='*70}")
    print(f"Action Type: {action_type.value}")
    print(f"Command: {command}")
    print(f"Target: {target_resource}")
    print(f"Agent: {agent_id} | Scope: {agent_scope}\n")

    # Create context
    context = ActionContext(
        action_type=action_type,
        command=command,
        target_resource=target_resource,
        agent_id=agent_id,
        agent_scope=agent_scope,
    )

    # Classify
    classifier = get_classifier()
    classification = classifier.classify(context)

    print(f"🤖 Classification: {classification.classification.value.upper()}")
    print(f"   Confidence: {classification.confidence:.0%}")
    print(f"   Reasoning: {classification.reasoning}\n")

    # Evaluate policy
    proxy = get_proxy()
    decision, reason = proxy.policy_engine.evaluate(context, classification)

    print(f"⚖️  Decision: {decision.upper()}")
    print(f"   Reason: {reason}\n")

    # Show result
    if decision == "blocked":
        print("🚫 ACTION BLOCKED")
        print("   This action would be prevented from executing.")
    elif decision == "approved":
        print("✅ ACTION APPROVED")
        print("   This action would be executed immediately.")
    else:
        print("⚠️  ACTION FLAGGED")
        print("   This action would be executed but flagged for review.")


def main():
    """Run demo scenarios."""
    print("\n" + "="*70)
    print("  AGENTFUSE DEMO - Agent Safety Layer")
    print("="*70)

    # Demo 1: Safe read operation
    demo_action(
        "Demo 1: Safe Read - Get application logs",
        ActionType.FILE_READ,
        "cat /var/log/app.log",
        "/var/log/app.log",
        "claude-dev",
        "staging",
    )

    # Demo 2: Reversible write
    demo_action(
        "Demo 2: Reversible Write - Update source code",
        ActionType.FILE_WRITE,
        "write src/utils.py (2500 bytes)",
        "src/utils.py",
        "claude-dev",
        "staging",
    )

    # Demo 3: Production delete (BLOCKED)
    demo_action(
        "Demo 3: DANGEROUS - Delete production database directory",
        ActionType.BASH_RUN,
        "rm -rf /data/postgres/prod_volume",
        "/data/postgres/prod_volume",
        "automated-task",
        "prod",
    )

    # Demo 4: Credential file access (BLOCKED)
    demo_action(
        "Demo 4: DANGEROUS - Access private SSH key",
        ActionType.FILE_READ,
        "cat /root/.ssh/id_rsa",
        "/root/.ssh/id_rsa",
        "claude-dev",
        "prod",
    )

    # Demo 5: Database delete without WHERE (BLOCKED)
    demo_action(
        "Demo 5: DANGEROUS - Delete all users from production database",
        ActionType.DB_DELETE,
        "DELETE FROM users",
        "prod_db",
        "automated-task",
        "prod",
    )

    # Demo 6: Config file modification (FLAGGED/BLOCKED)
    demo_action(
        "Demo 6: RISKY - Modify production config",
        ActionType.FILE_WRITE,
        "write /etc/hosts (500 bytes)",
        "/etc/hosts",
        "automated-task",
        "prod",
    )

    # Demo 7: Safe database query
    demo_action(
        "Demo 7: Safe Read - Query staging database",
        ActionType.DB_SELECT,
        "SELECT * FROM users WHERE id = 123",
        "staging_db",
        "claude-dev",
        "staging",
    )

    # Demo 8: Test run (GREEN)
    demo_action(
        "Demo 8: Safe - Run test suite",
        ActionType.BASH_RUN,
        "python -m pytest tests/",
        "/test",
        "claude-dev",
        "staging",
    )

    # Show summary
    print(f"\n{'='*70}")
    print("📊 Proxy Statistics")
    print(f"{'='*70}")

    proxy = get_proxy()
    stats = proxy.get_stats()

    print(f"Total Calls: {stats['total_calls']}")
    print(f"Approved: {stats['approved']} ({stats.get('approved', 0)/max(stats['total_calls'], 1):.0%})")
    print(f"Flagged: {stats['flagged']} ({stats.get('flagged', 0)/max(stats['total_calls'], 1):.0%})")
    print(f"Blocked: {stats['blocked']} ({stats['block_rate']:.0%})")
    print(f"Errors: {stats['errors']}")

    print(f"\n{'='*70}")
    print("✓ Demo complete!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
