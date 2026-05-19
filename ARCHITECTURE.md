# AgentFuse Architecture

## System Overview

AgentFuse is a safety layer that sits between AI agents and their tools. It intercepts all tool calls, classifies them for safety, and enforces policies before execution.

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent (Claude/Cursor)                    │
└────────────────────────┬────────────────────────────────────┘
                         │ All tool calls go here
┌────────────────────────▼────────────────────────────────────┐
│                    MCP Proxy Server                          │
│  - Intercepts tool calls                                     │
│  - Parses action type, target, scope                         │
│  - Routes to classifier & policy engine                      │
│  - Returns response (execute, block, or flag)                │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐  ┌──────▼──────┐  ┌─────▼───────┐
│  Classifier  │  │   Policy    │  │  Database   │
│  (DeBERTa)   │  │   Engine    │  │   Logger    │
│              │  │             │  │             │
│ Green/Yellow │  │ Scope rules │  │ Action logs │
│ Red          │  │ Policies    │  │ Alerts      │
└──────────────┘  └─────────────┘  └─────────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │  Response Generator             │
        │  - approve (execute)            │
        │  - block (return error)         │
        │  - flag (execute + log)         │
        └────────────────┬────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Real Tool (bash, file, db, api)                │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. MCP Proxy Server (`mcp_proxy.py`)

The entry point for all tool calls from agents.

**Key Classes:**
- `MCPProxy` - Main proxy class

**Key Methods:**
- `parse_action()` - Parse MCP request into ActionContext
- `intercept()` - Main interception logic
- `get_stats()` - Return proxy statistics

**Flow:**
```
MCP Request → Parse → Check Rules → Classify → Evaluate Policy → Respond
```

**Example:**
```python
request = MCPRequest(method="tools/call", params={"name": "bash", ...})
response, decision = proxy.intercept(request, agent_id="claude-dev", execute_fn=bash_execute)
# Returns: (MCPResponse(result=...), "approved"|"blocked"|"flagged")
```

### 2. DeBERTa Classifier (`classifier.py`)

Fine-tuned deep learning model for action classification.

**Key Classes:**
- `DeBERTaClassifier` - Loads and runs inference on fine-tuned model
- Falls back to baseline rule-based classifier if model unavailable

**Classification Output:**
```
ClassificationResult(
    classification=GREEN|YELLOW|RED,
    confidence=0.0-1.0,
    reasoning="..."
)
```

**Inference Pipeline:**
1. Convert ActionContext to text representation
2. Tokenize with BERT tokenizer
3. Forward pass through DeBERTa
4. Softmax over 3 classes
5. Return top prediction with confidence

**Latency:** <10ms on CPU

**Baseline Rules (when model unavailable):**
- Read operations → GREEN
- Writes → YELLOW
- Destructive + prod scope → RED
- Credential access → RED
- Config file modifications → RED/YELLOW based on scope

### 3. Policy Engine (`policy_engine.py`)

Converts classification into executable decisions based on agent policies.

**Key Classes:**
- `PolicyEngine` - Evaluates policies and makes decisions

**Decision Logic:**
```
Classification → Policy Rules → Decision (approve/block/flag)

GREEN  + any policy → APPROVED (execute immediately)
YELLOW + yellow_approval_required → BLOCKED (else FLAGGED)
RED    + red_approval_required → BLOCKED (else might be APPROVED if policy allows)
```

**Additional Rules Checked:**
- Config file access (prod scope = block)
- Credential file access (always block)
- Dangerous bash patterns (rm -rf, dd, mkfs, etc)

**Logging:**
- Logs to PostgreSQL Action table
- Creates alert logs for RED actions
- Records blocked actions separately
- Captures before-state snapshots

### 4. Database Models (`database.py`)

SQLAlchemy ORM models for logging.

**Tables:**
- `actions` - All executed/blocked/flagged actions
- `blocked_actions` - Blocked actions available for review
- `alert_logs` - Alerts for dangerous actions
- `agent_policies` - Per-agent policy configuration

**Indexes:**
- `idx_agent_timestamp` - Fast queries by agent
- `idx_classification` - Filter by safety class
- `idx_decision` - Filter by decision type

### 5. Configuration System (`config.py`)

Central configuration management.

**Settings:**
- Database connection
- Classifier model path
- Policy YAML file location
- MCP timeout
- Logging settings

**Policy Configuration (`policies.yaml`):**
```yaml
agents:
  agent_id:
    scope: staging|prod|prod_analytics_replica
    max_parallel_actions: 10
    require_approval_on_yellow: false
    require_approval_on_red: true
    
rules:
  prod_prefix: [prod_, production_]
  config_files: [/etc/, .env, config.yaml]
  dangerous_commands: [rm -rf, dd if=, mkfs]
```

### 6. FastAPI Application (`main.py`)

REST API for monitoring and management.

**Endpoints:**
- `GET /health` - Health check
- `GET /stats` - Overall statistics
- `GET /api/actions/recent` - Recent actions with filters
- `GET /api/actions/blocked` - Blocked actions
- `GET /api/actions/alerts` - Alerts

## Data Flow

### 1. Action Interception

```
Agent tool call (MCP format)
    ↓
MCPProxy.intercept()
    ↓
parse_action() → ActionContext
```

### 2. Classification

```
ActionContext
    ↓
convert to text → tokenize → DeBERTa forward pass → softmax
    ↓
ClassificationResult (class, confidence, reasoning)
```

### 3. Policy Evaluation

```
ClassificationResult + Agent Policy
    ↓
PolicyEngine.evaluate()
    ↓
Decision (approve/block/flag) + Reason
```

### 4. Action Execution

```
Approved:  Execute tool immediately, log result
Flagged:   Execute tool, create alert, log with before/after state
Blocked:   Return error response, don't execute, create alert
```

### 5. Logging

```
ActionLog record:
{
    action_id,
    agent_id,
    action_type,
    command,
    target_resource,
    classification,
    confidence,
    decision,
    reason,
    before_state,     # For YELLOW/RED
    after_state,      # Execution result
    timestamp,
    duration_ms
}
```

## Classification Details

### Green (Safe, Auto-Approve)
- **Examples:** cat, ls, SELECT queries, pytest, git status
- **Characteristics:** Reversible, read-only, no risk
- **Decision:** Execute immediately with no approval needed
- **Logging:** Minimal - action_id + metadata

### Yellow (Risky, Proceed with Caution)
- **Examples:** File writes (non-critical), INSERT/UPDATE, npm install, git commit
- **Characteristics:** Reversible within 24h, captured before-state
- **Decision:** Execute but flag for review
- **Logging:** Full before/after state captured
- **Alert Level:** Medium

### Red (Destructive, Block)
- **Examples:** rm -rf /prod_*, DELETE without WHERE, credential access, /etc/ writes
- **Characteristics:** Irreversible, destructive, security risk
- **Decision:** Block execution, require manual approval
- **Logging:** Detailed before-state, alert created immediately
- **Alert Level:** Critical

## Agent Scopes

Agents can operate in different scopes:

- **staging** - Non-production, low restriction
- **prod_analytics_replica** - Production analytics, restricted but not critical
- **prod** - Production, highest restriction
- **prod_<service>** - Service-specific production scope

Production detection:
```python
is_prod = any(scope.startswith(prefix) for prefix in ["prod_", "production_"])
```

## Training Data Generation

Synthetic dataset for DeBERTa fine-tuning:

```
500 examples total:
- 250 GREEN (reads, queries, tests)
- 150 YELLOW (writes, updates, installs)
- 100 RED (deletes, credential access, config mods)
```

Format: JSONL with text representation and label

```json
{"text": "Action: file_read | Command: cat ... | Target: ... | Scope: ...", "label": "green"}
```

## Fallback & Resilience

**If classifier fails:**
- Use baseline rule-based classifier
- All rules still applied (prod scope = red, creds = red, etc)
- Agent can still work but with conservative classifications

**If database fails:**
- Logging fails gracefully
- Decisions still made based on classification
- Errors are caught and logged to stdout

**If policy config fails:**
- Load default policies
- All agents use "staging" scope by default
- Conservative approach (more things flagged/blocked)

## Security Considerations

### Injection Defense
- Command/path strings are not executed
- Only logged and classified as text
- No arbitrary code execution path

### Database Security
- Use parameterized queries (SQLAlchemy)
- No SQL injection possible
- Connection pooling with timeout

### Classification Model
- Runs locally, no external API calls
- Fast inference (<10ms)
- Baseline rules as safety net

### Audit Trail
- All decisions logged to database
- Before/after states captured
- Full action history available for review

## Performance Characteristics

| Operation | Latency | Throughput |
|-----------|---------|-----------|
| Parse action | <1ms | >10k/sec |
| Classify (ML) | 8-10ms | 100/sec |
| Classify (baseline) | 2-3ms | 300/sec |
| Policy eval | <1ms | >10k/sec |
| Database log | 5-10ms | 100/sec |
| **Total intercept** | **15-20ms** | **50/sec** |

*Note: Baseline classifier used when DeBERTa model not available*

## Future Enhancements (Days 3-7)

### Day 3: Advanced Policy Engine
- Scope-based restrictions
- Resource quota enforcement
- Parallel action limits
- Blast radius calculation

### Day 4: Rollback & Recovery
- Before-state snapshots with versioning
- Compensating transaction design
- Rollback API
- Point-in-time recovery

### Day 5: Dashboard & Alerts
- FastAPI expansion
- Slack bot integration
- Next.js dashboard with live feed
- Email alerts

### Day 6: Production Deployment
- AWS deployment
- Terraform infrastructure
- GitHub Actions CI/CD
- Langfuse + W&B integration

### Day 7: Demonstration
- Production agent scenario
- Live blocking demonstration
- One-click rollback demo
- ROI calculations

## Development Guidelines

### Adding a New Action Type
1. Add to `ActionType` enum in `schemas.py`
2. Update `_map_tool_to_action_type()` in `mcp_proxy.py`
3. Add classification rules in `classifier.py`
4. Add test in `tests/test_classifier.py`

### Adding a New Policy Rule
1. Add to `check_additional_rules()` in `policy_engine.py`
2. Update `policies.yaml` with configuration
3. Add test in `tests/test_policy_engine.py`
4. Document in ARCHITECTURE.md

### Extending Classification
1. Add examples to `generate_training_data.py`
2. Regenerate dataset: `python scripts/generate_training_data.py`
3. Retrain model: `python scripts/train_classifier.py`
4. Test with `scripts/demo.py`

## Debugging

### Enable detailed logging
```bash
LOG_LEVEL=DEBUG python -m src.main
```

### Trace a specific action
```sql
SELECT * FROM actions WHERE action_id = 'xxx';
SELECT * FROM alert_logs WHERE action_id = 'xxx';
```

### Test classifier directly
```python
from src.classifier import get_classifier
from src.schemas import ActionContext, ActionType

c = get_classifier()
ctx = ActionContext(...)
result = c.classify(ctx)
print(f"{result.classification} ({result.confidence:.0%})")
```

### Check proxy stats
```bash
curl http://localhost:8000/proxy/stats
```
