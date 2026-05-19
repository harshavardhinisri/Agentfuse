"""Database models and connection management."""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, JSON, Enum, Index,
    create_engine, event, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool

from src.config import get_settings
from src.schemas import ActionClassification, ActionType


Base = declarative_base()


class Action(Base):
    """Logged action record in database."""

    __tablename__ = "actions"

    action_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(100), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    command = Column(String(2000), nullable=False)
    target_resource = Column(String(500), nullable=False)
    classification = Column(String(20), nullable=False)  # green, yellow, red
    confidence = Column(Float, nullable=False)
    decision = Column(String(50), nullable=False)  # approved, blocked, flagged
    reason = Column(String(500))
    before_state = Column(JSON)  # Before-state snapshot
    after_state = Column(JSON)   # Execution result
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    duration_ms = Column(Float, default=0.0)

    __table_args__ = (
        Index("idx_agent_timestamp", "agent_id", "timestamp"),
        Index("idx_classification", "classification"),
        Index("idx_decision", "decision"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "command": self.command,
            "target_resource": self.target_resource,
            "classification": self.classification,
            "confidence": self.confidence,
            "decision": self.decision,
            "reason": self.reason,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration_ms": self.duration_ms,
        }


class AgentPolicy(Base):
    """Per-agent policy configuration."""

    __tablename__ = "agent_policies"

    agent_id = Column(String(100), primary_key=True)
    scope = Column(String(100), nullable=False)  # staging, prod, etc
    max_parallel_actions = Column(Integer, default=10)
    require_approval_on_yellow = Column(Boolean, default=False)
    require_approval_on_red = Column(Boolean, default=True)
    auto_rollback_on_error = Column(Boolean, default=True)
    allowed_action_types = Column(JSON)  # List of allowed ActionType values
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "scope": self.scope,
            "max_parallel_actions": self.max_parallel_actions,
            "require_approval_on_yellow": self.require_approval_on_yellow,
            "require_approval_on_red": self.require_approval_on_red,
            "auto_rollback_on_error": self.auto_rollback_on_error,
            "allowed_action_types": self.allowed_action_types,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BlockedAction(Base):
    """Record of blocked actions for review/replay."""

    __tablename__ = "blocked_actions"

    action_id = Column(String(36), primary_key=True)
    agent_id = Column(String(100), nullable=False, index=True)
    command = Column(String(2000), nullable=False)
    target_resource = Column(String(500), nullable=False)
    reason = Column(String(500))
    blocked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    approved = Column(Boolean)
    approval_reason = Column(String(500))

    __table_args__ = (
        Index("idx_blocked_agent_timestamp", "agent_id", "blocked_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "command": self.command,
            "target_resource": self.target_resource,
            "reason": self.reason,
            "blocked_at": self.blocked_at.isoformat() if self.blocked_at else None,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "approved": self.approved,
            "approval_reason": self.approval_reason,
        }


class AlertLog(Base):
    """Alert log for red/dangerous actions."""

    __tablename__ = "alert_logs"

    alert_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id = Column(String(36), nullable=False)
    agent_id = Column(String(100), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    command = Column(String(2000), nullable=False)
    severity = Column(String(20), nullable=False)  # "critical", "high", "medium"
    message = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime)

    __table_args__ = (
        Index("idx_alert_created", "created_at"),
        Index("idx_alert_agent", "agent_id", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "command": self.command,
            "severity": self.severity,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "notified": self.notified,
            "notified_at": self.notified_at.isoformat() if self.notified_at else None,
        }


class Snapshot(Base):
    """Before-state snapshot for rollback (Layer 4)."""

    __tablename__ = "snapshots"

    snapshot_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id = Column(String(36), nullable=False, index=True)
    agent_id = Column(String(100), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    target_resource = Column(String(500), nullable=False)
    snapshot_type = Column(String(50), nullable=False)  # "file", "database", "directory"
    before_state = Column(JSON, nullable=False)  # Metadata about before state
    content_key = Column(String(500))  # S3 key or local path for actual content
    content_hash = Column(String(64))  # SHA256 hash for integrity checking
    size_bytes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_snapshot_action", "action_id"),
        Index("idx_snapshot_agent", "agent_id", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "target_resource": self.target_resource,
            "snapshot_type": self.snapshot_type,
            "before_state": self.before_state,
            "content_key": self.content_key,
            "content_hash": self.content_hash,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Rollback(Base):
    """Rollback transaction record (Layer 5)."""

    __tablename__ = "rollbacks"

    rollback_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiated_by = Column(String(100), nullable=False)  # User or system
    initiated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    rollback_to_action_id = Column(String(36), nullable=False, index=True)  # Checkpoint
    actions_to_rollback = Column(JSON, nullable=False)  # List of action IDs to undo
    status = Column(String(20), nullable=False, default="pending")  # pending, in_progress, completed, failed
    compensating_transactions = Column(JSON)  # Generated inverse operations
    executed_transactions = Column(JSON)  # Transactions actually executed
    completion_time = Column(DateTime)
    error_message = Column(String(1000))

    __table_args__ = (
        Index("idx_rollback_initiated", "initiated_at"),
        Index("idx_rollback_status", "status"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "rollback_id": self.rollback_id,
            "initiated_by": self.initiated_by,
            "initiated_at": self.initiated_at.isoformat() if self.initiated_at else None,
            "rollback_to_action_id": self.rollback_to_action_id,
            "actions_to_rollback": self.actions_to_rollback,
            "status": self.status,
            "compensating_transactions": self.compensating_transactions,
            "executed_transactions": self.executed_transactions,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "error_message": self.error_message,
        }


class ScopeRule(Base):
    """Deterministic scope rules for agents (Layer 3)."""

    __tablename__ = "scope_rules"

    rule_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(100), nullable=False, index=True)
    rule_type = Column(String(50), nullable=False)  # "allowed_path", "blocked_path", "allowed_db", "blocked_db", "blocked_shell"
    pattern = Column(String(500), nullable=False)  # Pattern to match
    operation = Column(String(100))  # Specific operation if applicable (optional)
    description = Column(String(500))
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_scope_agent", "agent_id", "rule_type"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "agent_id": self.agent_id,
            "rule_type": self.rule_type,
            "pattern": self.pattern,
            "operation": self.operation,
            "description": self.description,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentStatus(Base):
    """Agent runtime status and health (Layer 6 - Kill Switch)."""

    __tablename__ = "agent_status"

    agent_id = Column(String(100), primary_key=True)
    status = Column(String(50), nullable=False, default="running")  # running, halted, suspended, error
    halted_at = Column(DateTime)  # When kill switch was activated
    halted_by = Column(String(100))  # User or system that halted
    halt_reason = Column(String(500))  # Reason for halt
    current_action_id = Column(String(36))  # In-flight action if any
    last_action_at = Column(DateTime, index=True)  # Last action timestamp
    action_count_today = Column(Integer, default=0)  # Actions completed today
    error_count = Column(Integer, default=0)  # Errors encountered
    last_error = Column(String(500))  # Last error message
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_status_halted", "halted_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "halted_at": self.halted_at.isoformat() if self.halted_at else None,
            "halted_by": self.halted_by,
            "halt_reason": self.halt_reason,
            "current_action_id": self.current_action_id,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "action_count_today": self.action_count_today,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class HaltEvent(Base):
    """Record of halt/kill switch events (Layer 6)."""

    __tablename__ = "halt_events"

    halt_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(100), nullable=False, index=True)
    initiated_by = Column(String(100), nullable=False)  # User or automation
    initiated_via = Column(String(50), nullable=False)  # "api" or "slack"
    reason = Column(String(500), nullable=False)
    last_action_id = Column(String(36))  # Last action that was running
    halted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    halt_duration_ms = Column(Float)  # Time to fully halt
    actions_pending = Column(Integer)  # Actions that were cancelled
    rollback_generated = Column(Boolean, default=False)  # Whether compensating transactions were generated
    slack_notified = Column(Boolean, default=False)  # Whether Slack notification was sent

    __table_args__ = (
        Index("idx_halt_agent", "agent_id", "halted_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "halt_id": self.halt_id,
            "agent_id": self.agent_id,
            "initiated_by": self.initiated_by,
            "initiated_via": self.initiated_via,
            "reason": self.reason,
            "last_action_id": self.last_action_id,
            "halted_at": self.halted_at.isoformat() if self.halted_at else None,
            "halt_duration_ms": self.halt_duration_ms,
            "actions_pending": self.actions_pending,
            "rollback_generated": self.rollback_generated,
            "slack_notified": self.slack_notified,
        }


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self):
        """Initialize database manager."""
        settings = get_settings()
        self.engine = create_engine(
            settings.database_url,
            poolclass=QueuePool,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            echo=settings.debug,
            connect_args={"connect_timeout": 10},
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

        # Listen for disconnect events and reconnect
        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Set connection parameters on connect."""
            pass

        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Test connection health on checkout."""
            try:
                dbapi_conn.isolation_level
            except Exception:
                raise InvalidRequestError("Connection failed health check")

    def init_db(self) -> None:
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()

    def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False

    def close(self) -> None:
        """Close database connections."""
        self.engine.dispose()


# Global database manager
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db_session() -> Session:
    """Get a database session."""
    return get_db_manager().get_session()


class InvalidRequestError(Exception):
    """Invalid request error."""
    pass
