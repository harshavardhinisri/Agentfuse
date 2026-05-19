"""Tests for MCP proxy."""

import pytest
from src.mcp_proxy import MCPProxy
from src.schemas import MCPRequest, ActionType


@pytest.fixture
def proxy():
    """Create MCP proxy instance."""
    return MCPProxy()


def test_proxy_initialization(proxy):
    """Test proxy initializes correctly."""
    assert proxy is not None
    assert proxy.classifier is not None
    assert proxy.policy_engine is not None
    assert proxy.stats["total_calls"] == 0


def test_parse_bash_action(proxy):
    """Test parsing bash tool call."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "bash",
            "arguments": {"command": "ls -la /tmp"},
        },
    )

    context = proxy.parse_action(request, "test-agent")

    assert context is not None
    assert context.action_type == ActionType.BASH_RUN
    assert context.command == "ls -la /tmp"
    assert context.agent_id == "test-agent"


def test_parse_file_read_action(proxy):
    """Test parsing file read tool call."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "read_file",
            "arguments": {"path": "/var/log/app.log"},
        },
    )

    context = proxy.parse_action(request, "test-agent")

    assert context is not None
    assert context.action_type == ActionType.FILE_READ
    assert context.target_resource == "/var/log/app.log"


def test_parse_file_write_action(proxy):
    """Test parsing file write tool call."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "write_file",
            "arguments": {
                "path": "/src/utils.py",
                "content": "def helper(): pass",
            },
        },
    )

    context = proxy.parse_action(request, "test-agent")

    assert context is not None
    assert context.action_type == ActionType.FILE_WRITE
    assert context.target_resource == "/src/utils.py"


def test_parse_db_select_action(proxy):
    """Test parsing database SELECT query."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "query_db",
            "arguments": {
                "query": "SELECT * FROM users WHERE id = 123",
                "database": "staging_db",
            },
        },
    )

    context = proxy.parse_action(request, "test-agent")

    assert context is not None
    assert context.action_type == ActionType.DB_SELECT
    assert context.target_resource == "staging_db"


def test_parse_db_delete_action(proxy):
    """Test parsing database DELETE query."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "execute_sql",
            "arguments": {
                "query": "DELETE FROM users",
                "database": "prod_db",
            },
        },
    )

    context = proxy.parse_action(request, "test-agent")

    assert context is not None
    assert context.action_type == ActionType.DB_DELETE
    assert context.target_resource == "prod_db"


def test_credentials_detection(proxy):
    """Test credential file detection."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "read_file",
            "arguments": {"path": "/root/.ssh/id_rsa"},
        },
    )

    context = proxy.parse_action(request, "test-agent")

    assert context is not None
    assert context.touches_credentials


def test_env_file_detection(proxy):
    """Test .env file detection."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "read_file",
            "arguments": {"path": ".env"},
        },
    )

    context = proxy.parse_action(request, "test-agent")

    assert context is not None
    assert context.touches_credentials


def test_stats_tracking(proxy):
    """Test proxy tracks statistics."""
    assert proxy.stats["total_calls"] == 0

    # Create dummy context
    from src.schemas import ActionContext

    context = ActionContext(
        action_type=ActionType.FILE_READ,
        command="cat /tmp/test.txt",
        target_resource="/tmp/test.txt",
        agent_id="test-agent",
        agent_scope="staging",
    )

    # Would need to actually call intercept to test
    # For now, just verify stats exist
    stats = proxy.get_stats()

    assert "total_calls" in stats
    assert "approved" in stats
    assert "blocked" in stats
    assert "flagged" in stats
    assert "errors" in stats
    assert "block_rate" in stats


def test_unknown_tool_passthrough(proxy):
    """Test unknown tools pass through."""
    request = MCPRequest(
        method="tools/call",
        params={
            "name": "unknown_tool",
            "arguments": {"some_arg": "value"},
        },
    )

    context = proxy.parse_action(request, "test-agent")

    # Unknown tool should return None
    assert context is None
