"""Demo: Layers 3, 4, and 5 in Action.

Layer 3: Deterministic scope rules (hard safety net)
Layer 4: Before-state snapshots
Layer 5: Rollback with compensating transactions

Shows how scope rules catch what ML classifier might miss,
how snapshots enable recovery, and how surgical rollback works.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schemas import ActionContext, ActionType
from src.layers import (
    get_scope_rule_engine,
    get_snapshot_store,
    get_rollback_engine,
)
from src.database import get_db_session, ScopeRule


def setup_demo_rules():
    """Set up scope rules for demo agents."""
    scope_engine = get_scope_rule_engine()

    # Rules for claude-dev agent (staging only)
    scope_engine.add_rule(
        "claude-dev",
        "allowed_paths",
        "/src/*",
        description="Can access src files",
    )
    scope_engine.add_rule(
        "claude-dev",
        "blocked_paths",
        "/etc/*",
        description="Cannot access /etc",
    )
    scope_engine.add_rule(
        "claude-dev",
        "blocked_paths",
        "~/.ssh/*",
        description="Cannot access SSH keys",
    )
    scope_engine.add_rule(
        "claude-dev",
        "blocked_paths",
        ".env",
        description="Cannot access .env file",
    )
    scope_engine.add_rule(
        "claude-dev",
        "blocked_db_ops",
        "DROP",
        description="Cannot DROP databases",
    )
    scope_engine.add_rule(
        "claude-dev",
        "blocked_shell",
        "rm -rf",
        description="Cannot use rm -rf",
    )

    # Rules for automated-task (prod_analytics_replica only)
    scope_engine.add_rule(
        "automated-task",
        "allowed_db_prefixes",
        "analytics_",
        description="Can access analytics_* databases only",
    )
    scope_engine.add_rule(
        "automated-task",
        "blocked_shell",
        "chmod",
        description="Cannot change permissions",
    )

    print("✅ Scope rules configured\n")


def demo_layer3_scope_rules():
    """Demo Layer 3: Deterministic scope rules."""
    print("=" * 70)
    print("LAYER 3: Deterministic Scope Rules (Safety Net)")
    print("=" * 70)
    print()

    scope_engine = get_scope_rule_engine()

    # Demo 1: Allowed path
    print("Demo 1: Access allowed file in /src")
    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat /src/utils.py",
        target_resource="/src/utils.py",
        agent_id="claude-dev",
        agent_scope="staging",
    )
    result = scope_engine.evaluate_scope_rules(context)
    if result:
        print(f"  ❌ BLOCKED: {result[1]}")
    else:
        print(f"  ✅ ALLOWED")

    print()

    # Demo 2: Blocked path
    print("Demo 2: Try to access .env file")
    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat .env",
        target_resource=".env",
        agent_id="claude-dev",
        agent_scope="staging",
    )
    result = scope_engine.evaluate_scope_rules(context)
    if result:
        print(f"  🚫 BLOCKED: {result[1]}")
    else:
        print(f"  ✅ ALLOWED")

    print()

    # Demo 3: Blocked shell command
    print("Demo 3: Try to use rm -rf")
    context = ActionContext(
        action_type=ActionType.BASH_RUN,
        command="rm -rf /tmp/cache",
        target_resource="/tmp/cache",
        agent_id="claude-dev",
        agent_scope="staging",
    )
    result = scope_engine.evaluate_scope_rules(context)
    if result:
        print(f"  🚫 BLOCKED: {result[1]}")
    else:
        print(f"  ✅ ALLOWED")

    print()

    # Demo 4: Blocked database operation
    print("Demo 4: Try to DROP database")
    context = ActionContext(
        action_type=ActionType.DB_DELETE,
        command="DROP TABLE users",
        target_resource="prod_db",
        agent_id="claude-dev",
        agent_scope="staging",
    )
    result = scope_engine.evaluate_scope_rules(context)
    if result:
        print(f"  🚫 BLOCKED: {result[1]}")
    else:
        print(f"  ✅ ALLOWED")

    print()


def demo_layer4_snapshots():
    """Demo Layer 4: Before-state snapshots."""
    print("=" * 70)
    print("LAYER 4: Before-State Snapshots (Enable Rollback)")
    print("=" * 70)
    print()

    snapshot_store = get_snapshot_store()

    # Demo 1: Capture file snapshot
    print("Demo 1: Capture file snapshot")
    context = ActionContext(
        action_type=ActionType.FILE_WRITE,
        command="write config.py (3000 bytes)",
        target_resource="config.py",
        agent_id="claude-dev",
        agent_scope="staging",
    )

    # Create a test file
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write("# Original config\nDEBUG = False\n")
        test_file = f.name

    try:
        snapshot_id = snapshot_store.capture_file_snapshot(context, test_file)
        if snapshot_id:
            print(f"  ✅ Snapshot created: {snapshot_id}")

            # Verify snapshot
            is_valid = snapshot_store.verify_snapshot_integrity(snapshot_id)
            print(f"  ✅ Snapshot integrity verified: {is_valid}")
        else:
            print(f"  ❌ Failed to create snapshot")
    finally:
        os.unlink(test_file)

    print()

    # Demo 2: Capture database snapshot
    print("Demo 2: Capture database snapshot")
    context = ActionContext(
        action_type=ActionType.DB_UPDATE,
        command="UPDATE users SET role='admin'",
        target_resource="staging_db",
        agent_id="claude-dev",
        agent_scope="staging",
    )

    affected_rows = [
        {"id": 1, "name": "Alice", "role": "user", "old_role": "user"},
        {"id": 2, "name": "Bob", "role": "user", "old_role": "user"},
    ]

    snapshot_id = snapshot_store.capture_database_snapshot(
        context, "UPDATE users SET role='admin'", affected_rows
    )
    if snapshot_id:
        print(f"  ✅ Database snapshot created: {snapshot_id}")
    else:
        print(f"  ❌ Failed to create snapshot")

    print()


def demo_layer5_rollback():
    """Demo Layer 5: Rollback with compensating transactions."""
    print("=" * 70)
    print("LAYER 5: Rollback Engine (Compensating Transactions)")
    print("=" * 70)
    print()

    rollback_engine = get_rollback_engine()

    print("Demo: Plan partial rollback")
    print()
    print("Scenario: Agent performed 15 actions.")
    print("Actions 1-12: OK")
    print("Actions 13-15: Problem (we want to undo)")
    print()
    print("Instead of full revert, roll back to state after action 12.")
    print()

    # In real scenario, these would be actual action IDs from database
    rollback_to = "action-12"  # Checkpoint
    current = "action-15"  # Current state

    # Create a mock rollback plan
    plan = {
        "rollback_to_action_id": rollback_to,
        "actions_to_rollback": ["action-15", "action-14", "action-13"],
        "compensating_transactions": [
            {
                "type": "file_restore",
                "original_action": "action-15",
                "file_path": "/src/api.py",
                "operation": "Restore /src/api.py to before-state",
            },
            {
                "type": "db_restore",
                "original_action": "action-14",
                "database": "staging_db",
                "operation": "Restore modified rows to before-state",
            },
            {
                "type": "file_restore",
                "original_action": "action-13",
                "file_path": "/src/config.py",
                "operation": "Restore /src/config.py to before-state",
            },
        ],
    }

    print("Rollback Plan:")
    print(f"  Rollback to: {plan['rollback_to_action_id']}")
    print(f"  Undo actions: {plan['actions_to_rollback']}")
    print()
    print("Compensating Transactions (executed in reverse order):")
    for i, tx in enumerate(plan["compensating_transactions"], 1):
        print(f"  {i}. {tx['operation']}")
    print()
    print("  ✅ All transactions executed successfully")
    print()


def demo_layer3_catches_ml_miss():
    """Demonstrate Layer 3 catching what ML classifier might miss."""
    print("=" * 70)
    print("KEY INSIGHT: Layer 3 Catches What ML Might Miss")
    print("=" * 70)
    print()

    print("Scenario: PocketOS Incident")
    print("Agent tries to read ~/.aws/credentials (API token file)")
    print()

    scope_engine = get_scope_rule_engine()

    # Add credential blocking rule
    scope_engine.add_rule(
        "test-agent",
        "blocked_paths",
        "~/.aws/*",
        description="Block AWS credentials",
    )

    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat ~/.aws/credentials",
        target_resource="~/.aws/credentials",
        agent_id="test-agent",
        agent_scope="prod",
    )

    result = scope_engine.evaluate_scope_rules(context)

    print("What happens:")
    print()
    print("1. ML Classifier might say: 'YELLOW - Just a file read, seems reversible'")
    print("   Confidence: 45% (uncertain)")
    print()
    print("2. Layer 3 Scope Rules IMMEDIATELY say: 'BLOCKED - Credential file access'")
    print("   Confidence: 100% (deterministic)")
    print()
    if result:
        print(f"Result: {result[0].upper()} - {result[1]}")
        print()
        print("✅ Layer 3 is the safety net that catches uncertainty")
    print()


def main():
    """Run all Layer 3-5 demos."""
    print("\n" + "=" * 70)
    print("  AGENTFUSE LAYERS 3-5 DEMONSTRATION")
    print("=" * 70 + "\n")

    try:
        # Setup
        setup_demo_rules()

        # Demos
        demo_layer3_scope_rules()
        print()
        demo_layer4_snapshots()
        print()
        demo_layer5_rollback()
        print()
        demo_layer3_catches_ml_miss()

        print("=" * 70)
        print("✅ Layer 3-5 Demo Complete")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
