"""Pydantic schemas for AgentFuse."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ActionClassification(str, Enum):
    """Safety classification for agent actions."""
    GREEN = "green"      # Auto-approve, reversible
    YELLOW = "yellow"    # Log + proceed, reversible with snapshot
    RED = "red"          # Block, destructive


class ActionType(str, Enum):
    """Types of actions agents can take."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    DIR_LIST = "dir_list"
    BASH_RUN = "bash_run"
    DB_SELECT = "db_select"
    DB_INSERT = "db_insert"
    DB_UPDATE = "db_update"
    DB_DELETE = "db_delete"
    API_CALL = "api_call"
    GIT_COMMAND = "git_command"
    UNKNOWN = "unknown"


class MCPRequest(BaseModel):
    """Raw MCP tool call request."""
    method: str
    params: dict[str, Any]
    id: Optional[str] = None


class MCPResponse(BaseModel):
    """MCP response format."""
    result: Optional[Any] = None
    error: Optional[str] = None
    id: Optional[str] = None


class ActionContext(BaseModel):
    """Context around an action for classification."""
    action_type: ActionType
    command: str
    target_resource: str
    agent_id: str
    agent_scope: str  # e.g., "staging", "prod_analytics_replica"
    recent_actions: list[str] = Field(default_factory=list)  # Last 5 action types
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_prod: bool = False  # Inferred from target_resource
    touches_credentials: bool = False
    touches_config: bool = False


class ClassificationResult(BaseModel):
    """Result from DeBERTa classifier."""
    classification: ActionClassification
    confidence: float  # 0-1
    reasoning: Optional[str] = None
    model_version: str = "1.0"


class ActionLog(BaseModel):
    """Logged action record."""
    action_id: str
    agent_id: str
    action_type: ActionType
    command: str
    target_resource: str
    classification: ActionClassification
    confidence: float
    decision: str  # "approved", "blocked", "flagged"
    reason: Optional[str] = None
    before_state: Optional[dict[str, Any]] = None  # Before-state snapshot
    after_state: Optional[dict[str, Any]] = None   # Execution result
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0


class ActionRequest(BaseModel):
    """Request to execute an action (for manual approval, replay, etc)."""
    action_id: str
    approved_by: str
    approval_reason: Optional[str] = None


class HealthResponse(BaseModel):
    """Server health status."""
    status: str  # "healthy", "degraded", "unhealthy"
    model_loaded: bool
    db_connected: bool
    classifier_latency_ms: float
    uptime_seconds: float


class StatsResponse(BaseModel):
    """Action statistics."""
    total_actions_logged: int
    green_count: int
    yellow_count: int
    red_count: int
    blocked_actions: int
    actions_today: int
    avg_classification_time_ms: float


class AgentConfig(BaseModel):
    """Per-agent configuration."""
    agent_id: str
    scope: str  # e.g., "staging", "prod", "prod_analytics_replica"
    max_parallel_actions: int = 10
    require_approval_on_yellow: bool = False
    require_approval_on_red: bool = True
    auto_rollback_on_error: bool = True
    allowed_action_types: Optional[list[ActionType]] = None  # None = all allowed


class PolicyTemplate(BaseModel):
    """Predefined policy templates."""
    name: str  # "permissive", "strict", "prod"
    allow_green: bool = True
    allow_yellow: bool = True
    allow_red: bool = False
    require_approval_on_yellow: bool = False
    require_approval_on_red: bool = True
