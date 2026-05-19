# AgentFuse Quick Start Guide

## Problem

AI agents in production can execute destructive actions (delete databases, corrupt configs, revert patches) and 60% of organizations have no way to stop them.

## Solution

AgentFuse intercepts all agent tool calls, classifies them as safe/risky/destructive, and enforces policies before execution.

## Architecture

```
Agent (Claude/Cursor)
    ↓
[AgentFuse MCP Proxy] ← Intercepts all tool calls (bash, file, db, api)
    ↓
[DeBERTa Classifier] ← Green/Yellow/Red classification (<10ms)
    ↓
[Policy Engine] ← Apply scope rules, enforce controls
    ↓
Real Tool (or BLOCK)
```

## What's Built (Days 1-2)

**Day 1: MCP Proxy Server**
- Intercepts all tool calls from Claude/Cursor agents
- Logs every action to PostgreSQL
- Routes to classifier and policy engine
- Blocks destructive actions before execution

**Day 2: DeBERTa Classifier**
- Fine-tuned on synthetic agent action dataset (500 examples)
- 3-class classification: Green (safe) / Yellow (risky) / Red (destructive)
- Sub-10ms inference latency
- Baseline rules when model unavailable

## Installation

### 1. Clone repo
```bash
cd /Users/harsha/projects/Agentfuse
```

### 2. Create environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -e ".[dev]"
```

### 4. Set up PostgreSQL
```bash
# On macOS with Homebrew:
brew install postgresql
brew services start postgresql

# Create database
createdb agentfuse
```

### 5. Configure
```bash
cp .env.example .env
# Edit .env with your PostgreSQL connection string if needed
```

### 6. Initialize database
```bash
python scripts/generate_training_data.py  # Generate synthetic dataset
python scripts/train_classifier.py        # Fine-tune DeBERTa (optional)
python -m alembic upgrade head            # Create tables
```

## Run the Demo

```bash
python scripts/demo.py
```

This will show you:
- 🟢 Safe read (approved)
- 🟡 Reversible write (flagged)
- 🔴 Production delete (BLOCKED)
- 🔴 Credential access (BLOCKED)
- 🔴 Database delete without WHERE (BLOCKED)

Output:
```
AGENTFUSE DEMO - Agent Safety Layer

Demo 1: Safe Read - Get application logs
Action Type: file_read
Command: cat /var/log/app.log
Classification: GREEN (95% confidence)
Decision: APPROVED

Demo 3: DANGEROUS - Delete production database directory
Action Type: bash_run
Command: rm -rf /data/postgres/prod_volume
Classification: RED (99% confidence)
Decision: BLOCKED
🚫 ACTION BLOCKED - This action would be prevented from executing.

[... more demos ...]

Proxy Statistics
Total Calls: 8
Approved: 3 (37%)
Flagged: 2 (25%)
Blocked: 3 (37%)
```

## Run the Server

```bash
python -m src.main
```

Server starts at `http://localhost:8000`

### Health Check
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "db_connected": true,
  "classifier_latency_ms": 8.5,
  "uptime_seconds": 12.3
}
```

### Get Stats
```bash
curl http://localhost:8000/stats
```

Response:
```json
{
  "total_actions_logged": 42,
  "green_count": 18,
  "yellow_count": 16,
  "red_count": 8,
  "blocked_actions": 7,
  "actions_today": 42,
  "avg_classification_time_ms": 7.2
}
```

### Get Recent Actions
```bash
curl http://localhost:8000/api/actions/recent?limit=10&classification=red
```

Response:
```json
[
  {
    "action_id": "abc123",
    "agent_id": "claude-dev",
    "action_type": "bash_run",
    "command": "rm -rf /data/postgres/prod_volume",
    "target_resource": "/data/postgres/prod_volume",
    "classification": "red",
    "confidence": 0.99,
    "decision": "blocked",
    "reason": "RED classification | Dangerous bash pattern detected",
    "timestamp": "2024-05-19T10:23:45.123Z",
    "duration_ms": 8.5
  }
]
```

## Configuration

Edit `config/policies.yaml` to customize:

```yaml
agents:
  claude-dev:
    scope: staging              # Agent operates in staging
    require_approval_on_red: true
    require_approval_on_yellow: false

  automated-task:
    scope: prod_analytics_replica  # Restricted to analytics replica
    require_approval_on_yellow: true
    require_approval_on_red: true
```

## Classification Rules

### 🟢 Green (Auto-approve)
- Read operations (cat, ls, SELECT)
- Directory listing
- Test runs (pytest)
- Git status
- Reversible, no risk

### 🟡 Yellow (Log + proceed)
- File writes (src/utils.py)
- Database inserts/updates (staging)
- Package installations
- Reversible within 24h, captured before-state

### 🔴 Red (Block + alert)
- `rm -rf /prod_*`
- `DELETE FROM users`  (no WHERE clause)
- Credential file access (.env, .ssh, id_rsa)
- Config file modifications (/etc/hosts, config.yaml)
- Destructive operations
- Hard blocked, requires manual approval

## Test Suite

```bash
# Run all tests
pytest tests/ -v --cov=src

# Run specific test
pytest tests/test_classifier.py::test_classify_destructive_delete -v

# Generate coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

## API Endpoints

- `GET /` - Root
- `GET /health` - Health check
- `GET /stats` - Statistics
- `GET /proxy/stats` - Proxy statistics
- `GET /api/actions/recent` - Recent actions
- `GET /api/actions/by-agent/{agent_id}` - Agent actions
- `GET /api/actions/blocked` - Blocked actions
- `GET /api/actions/alerts` - Alerts
- `GET /api/actions/{action_id}` - Get specific action
- `POST /api/actions/mark-reviewed/{action_id}` - Mark reviewed

## Next: Days 3-7

Days 3-7 will add:
- Day 3: Policy engine with scope rules and blast radius enforcement
- Day 4: Before-state snapshots and rollback engine
- Day 5: FastAPI backend expansion, Slack integration, dashboard
- Day 6: AWS deployment, Terraform, GitHub Actions
- Day 7: Production demo and one-click rollback

## Key Components

| Module | Purpose |
|--------|---------|
| `classifier.py` | DeBERTa model for action classification |
| `mcp_proxy.py` | Intercepts all MCP tool calls |
| `policy_engine.py` | Evaluates decisions based on policy |
| `database.py` | SQLAlchemy models for logging |
| `config.py` | Configuration management |
| `main.py` | FastAPI application |
| `api/` | REST endpoints |

## Debugging

### Enable debug logging
```bash
# In .env
LOG_LEVEL=DEBUG

# Restart server
python -m src.main
```

### Check database
```bash
psql agentfuse

# See all actions
SELECT agent_id, action_type, classification, decision FROM actions;

# See blocked actions
SELECT agent_id, command, reason FROM blocked_actions;

# See alerts
SELECT agent_id, severity, message FROM alert_logs ORDER BY created_at DESC;
```

### Check classifier
```bash
python -c "
from src.classifier import get_classifier
from src.schemas import ActionContext, ActionType

c = get_classifier()
ctx = ActionContext(
    action_type=ActionType.FILE_READ,
    command='cat /tmp/test.txt',
    target_resource='/tmp/test.txt',
    agent_id='test',
    agent_scope='staging'
)
result = c.classify(ctx)
print(f'{result.classification} ({result.confidence:.0%}): {result.reasoning}')
"
```

## Troubleshooting

**Database connection error**
```
psql agentfuse  # Verify PostgreSQL is running
brew services restart postgresql
```

**Model not loading**
```
# Generate and train if needed
python scripts/generate_training_data.py
python scripts/train_classifier.py

# Or use baseline (automatically falls back)
```

**Port already in use**
```
# Change port in .env
PORT=8001
```

## Support

- Documentation: [README.md](README.md)
- Issues: Check logs in `logs/` directory
- Slack alerts: Configure in Day 5
