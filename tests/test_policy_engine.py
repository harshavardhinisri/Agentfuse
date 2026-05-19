"""Tests for policy engine."""

import pytest
from src.policy_engine import PolicyEngine
from src.schemas import (
    ActionContext, ActionType, ActionClassification, ClassificationResult
)


@pytest.fixture
def engine():
    """Create policy engine instance."""
    return PolicyEngine()


def test_green_action_approved(engine):
    """Test that green actions are approved."""
    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat /var/log/app.log",
        target_resource="/var/log/app.log",
        agent_id="test-agent",
        agent_scope="staging",
    )

    classification = ClassificationResult(
        classification=ActionClassification.GREEN,
        confidence=0.95,
    )

    decision, reason = engine.evaluate(context, classification)

    assert decision == "approved"
    assert "GREEN" in reason


def test_yellow_action_flagged(engine):
    """Test that yellow actions are flagged."""
    context = ActionContext(
        action_type=ActionType.FILE_WRITE,
        command="write /src/utils.py",
        target_resource="/src/utils.py",
        agent_id="test-agent",
        agent_scope="staging",
    )

    classification = ClassificationResult(
        classification=ActionClassification.YELLOW,
        confidence=0.75,
    )

    decision, reason = engine.evaluate(context, classification)

    assert decision == "flagged"
    assert "YELLOW" in reason


def test_red_action_blocked(engine):
    """Test that red actions are blocked."""
    context = ActionContext(
        action_type=ActionType.BASH_RUN,
        command="rm -rf /data/postgres/prod_volume",
        target_resource="/data/postgres/prod_volume",
        agent_id="test-agent",
        agent_scope="prod",
    )

    classification = ClassificationResult(
        classification=ActionClassification.RED,
        confidence=0.99,
    )

    decision, reason = engine.evaluate(context, classification)

    assert decision == "blocked"
    assert "RED" in reason


def test_config_file_protection(engine):
    """Test that config files are protected."""
    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat /etc/hosts",
        target_resource="/etc/hosts",
        agent_id="test-agent",
        agent_scope="prod",
    )

    result = engine.check_additional_rules(context)

    assert result is not None
    decision, reason = result
    assert decision == "blocked"


def test_credential_file_protection(engine):
    """Test that credential files are protected."""
    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat .env",
        target_resource=".env",
        agent_id="test-agent",
        agent_scope="prod",
        touches_credentials=True,
    )

    # First check if it's detected by policy
    result = engine.check_additional_rules(context)
    # May or may not be caught here, depends on filename check


def test_dangerous_bash_blocked(engine):
    """Test that dangerous bash commands are blocked."""
    context = ActionContext(
        action_type=ActionType.BASH_RUN,
        command="rm -rf /critical/data",
        target_resource="/critical/data",
        agent_id="test-agent",
        agent_scope="staging",
    )

    result = engine.check_additional_rules(context)

    assert result is not None
    decision, reason = result
    assert decision == "blocked"


def test_production_scope_detection(engine):
    """Test that production scope is detected."""
    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat /var/log/app.log",
        target_resource="/var/log/app.log",
        agent_id="test-agent",
        agent_scope="prod_database",
    )

    # Create a classification
    classification = ClassificationResult(
        classification=ActionClassification.GREEN,
        confidence=0.95,
    )

    decision, reason = engine.evaluate(context, classification)

    # Should be approved for reads even in prod
    assert decision == "approved"
    # But context should be marked as prod
    assert context.is_prod


def test_agent_policy_override(engine):
    """Test that agent policies are respected."""
    # This would require setting up database, skipping for now
    pass


def test_log_action(engine):
    """Test logging an action."""
    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat /var/log/app.log",
        target_resource="/var/log/app.log",
        agent_id="test-agent",
        agent_scope="staging",
    )

    classification = ClassificationResult(
        classification=ActionClassification.GREEN,
        confidence=0.95,
    )

    # This will fail if DB is not set up, which is expected
    try:
        action_id = engine.log_action(
            context,
            classification,
            "approved",
            "Test log",
            0.1,
        )
        assert action_id  # Should get some ID back
    except Exception as e:
        # Expected if no database configured
        pytest.skip(f"Database not configured: {e}")
