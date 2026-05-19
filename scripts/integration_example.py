"""Integration example: How to use AgentFuse from client code."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schemas import MCPRequest, ActionType, ActionContext
from src.mcp_proxy import get_proxy
from src.classifier import get_classifier
from src.policy_engine import get_policy_engine


def example_1_direct_classification():
    """Example 1: Directly classify an action."""
    print("\n" + "="*70)
    print("Example 1: Direct Classification")
    print("="*70)

    from src.schemas import ActionContext, ActionType

    context = ActionContext(
        action_type=ActionType.FILE_WRITE,
        command="write /src/config.yaml (1500 bytes)",
        target_resource="/src/config.yaml",
        agent_id="claude-dev",
        agent_scope="staging",
    )

    classifier = get_classifier()
    result = classifier.classify(context)

    print(f"Action: Write config file in staging")
    print(f"Classification: {result.classification.value.upper()}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Reasoning: {result.reasoning}")


def example_2_policy_evaluation():
    """Example 2: Classify then evaluate policy."""
    print("\n" + "="*70)
    print("Example 2: Classification + Policy Evaluation")
    print("="*70)

    from src.schemas import ActionContext, ActionType, ClassificationResult

    context = ActionContext(
        action_type=ActionType.BASH_RUN,
        command="rm -rf /critical/data",
        target_resource="/critical/data",
        agent_id="automated-task",
        agent_scope="prod_analytics_replica",
    )

    classifier = get_classifier()
    classification = classifier.classify(context)

    engine = get_policy_engine()
    decision, reason = engine.evaluate(context, classification)

    print(f"Action: Delete directory in prod scope")
    print(f"Classification: {classification.classification.value.upper()}")
    print(f"Policy Decision: {decision.upper()}")
    print(f"Reason: {reason}")


def example_3_mcp_proxy():
    """Example 3: Intercept MCP tool call through proxy."""
    print("\n" + "="*70)
    print("Example 3: MCP Proxy Interception")
    print("="*70)

    # This is how the proxy would be called from an MCP client
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "read_file",
            "arguments": {"path": "/root/.env"},
        },
    )

    proxy = get_proxy()

    # Parse the MCP request
    context = proxy.parse_action(request, agent_id="claude-dev")

    if context:
        print(f"Parsed Action Type: {context.action_type.value}")
        print(f"Target: {context.target_resource}")
        print(f"Touches Credentials: {context.touches_credentials}")

        # Classify
        classification = proxy.classifier.classify(context)
        print(f"Classification: {classification.classification.value.upper()}")

        # Evaluate
        decision, reason = proxy.policy_engine.evaluate(context, classification)
        print(f"Decision: {decision.upper()}")
        print(f"Reason: {reason}")


def example_4_batch_processing():
    """Example 4: Batch classify multiple actions."""
    print("\n" + "="*70)
    print("Example 4: Batch Classification")
    print("="*70)

    from src.schemas import ActionContext, ActionType

    actions = [
        ("Safe Read", ActionType.FILE_READ, "cat /var/log/app.log", "/var/log/app.log", "staging"),
        ("DB Query", ActionType.DB_SELECT, "SELECT * FROM users", "staging_db", "staging"),
        ("Dangerous", ActionType.BASH_RUN, "rm -rf /prod_data", "/prod_data", "prod"),
    ]

    classifier = get_classifier()

    for name, action_type, command, target, scope in actions:
        context = ActionContext(
            action_type=action_type,
            command=command,
            target_resource=target,
            agent_id="test-agent",
            agent_scope=scope,
        )
        result = classifier.classify(context)
        print(f"{name:20} → {result.classification.value.upper():6} ({result.confidence:.0%})")


def example_5_real_world_scenario():
    """Example 5: Real-world scenario - agent refactoring code."""
    print("\n" + "="*70)
    print("Example 5: Real-World Scenario - Code Refactoring")
    print("="*70)

    from src.schemas import ActionContext, ActionType

    # Simulate an agent making a series of tool calls
    tool_calls = [
        ("1. Read README", ActionType.FILE_READ, "cat README.md", "README.md", "staging"),
        ("2. List src/", ActionType.DIR_LIST, "ls -la src/", "src/", "staging"),
        ("3. Read module", ActionType.FILE_READ, "cat src/utils.py", "src/utils.py", "staging"),
        ("4. Write refactored", ActionType.FILE_WRITE, "write src/utils.py (3000 bytes)", "src/utils.py", "staging"),
        ("5. Run tests", ActionType.BASH_RUN, "pytest tests/ --cov", "tests/", "staging"),
        ("6. Git commit", ActionType.BASH_RUN, "git commit -m 'refactor: improve utils'", ".git/", "staging"),
    ]

    classifier = get_classifier()
    engine = get_policy_engine()

    print("Agent is refactoring code in staging environment:\n")

    for step, action_type, command, target, scope in tool_calls:
        context = ActionContext(
            action_type=action_type,
            command=command,
            target_resource=target,
            agent_id="claude-dev",
            agent_scope=scope,
        )

        classification = classifier.classify(context)
        decision, reason = engine.evaluate(context, classification)

        status = "✅" if decision == "approved" else ("⚠️" if decision == "flagged" else "🚫")
        print(f"{status} {step:25} → {decision.upper():8} ({classification.classification.value.upper()})")


def example_6_agent_policies():
    """Example 6: Different agent with different policies."""
    print("\n" + "="*70)
    print("Example 6: Agent Policies")
    print("="*70)

    from src.config import get_policy_config
    from src.schemas import ActionContext, ActionType

    policy_config = get_policy_config()

    agents = ["claude-dev", "automated-task", "cursor-agent"]

    print("Agent Scopes:\n")

    for agent_id in agents:
        config = policy_config.get_agent_config(agent_id)
        scope = config.get("scope", "unknown")
        is_prod = policy_config.is_prod_scope(scope)
        approval_yellow = config.get("require_approval_on_yellow", False)
        approval_red = config.get("require_approval_on_red", True)

        prod_indicator = "🔴 PROD" if is_prod else "🟢 STAGING"
        print(f"{agent_id:20} → {scope:30} {prod_indicator}")
        print(f"  Yellow requires approval: {approval_yellow}")
        print(f"  Red requires approval:    {approval_red}\n")


if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# AgentFuse Integration Examples")
    print("#"*70)

    try:
        example_1_direct_classification()
        example_2_policy_evaluation()
        example_3_mcp_proxy()
        example_4_batch_processing()
        example_5_real_world_scenario()
        example_6_agent_policies()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "#"*70)
    print("# Examples Complete")
    print("#"*70 + "\n")
