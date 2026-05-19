"""AgentFuse Layers - Defense in Depth Safety System.

Layer 1: MCP Proxy - Interception (Day 1)
Layer 2: DeBERTa Classifier - ML Classification (Day 2)
Layer 3: Scope Rules - Deterministic Safety Net
Layer 4: Snapshots - Before-State Capture
Layer 5: Rollback - Compensating Transactions
Layer 6: Kill Switch - Emergency Agent Halt
"""

from .layer3_scope_rules import get_scope_rule_engine, ScopeRuleEngine
from .layer4_snapshots import get_snapshot_store, SnapshotStore
from .layer5_rollback import get_rollback_engine, RollbackEngine
from .layer6_kill_switch import get_kill_switch, KillSwitch

__all__ = [
    "ScopeRuleEngine",
    "SnapshotStore",
    "RollbackEngine",
    "KillSwitch",
    "get_scope_rule_engine",
    "get_snapshot_store",
    "get_rollback_engine",
    "get_kill_switch",
]
