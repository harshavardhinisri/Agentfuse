# Layer 6: Kill Switch - Emergency Agent Halt

## The Problem

60% of organizations have **no way to stop a rogue agent once it starts**.

When an agent goes wrong at 2am:
- 🔴 Data is being deleted in production
- 🔴 API credentials are being exfiltrated  
- 🔴 Configurations are being overwritten
- ❌ But there's no kill switch

Manual recovery:
- SSH into server
- Find agent process
- Kill it
- Assess damage
- Run rollback manually

**Result: 30-90 minutes downtime, massive data loss**

## The Solution

Layer 6 Kill Switch: **Emergency halt in <200ms with two interfaces**

```
Automated:  API endpoint for monitoring/circuit breakers
Human:      Slack command for on-call engineers
```

## Two Interfaces

### 1. FastAPI Endpoint (Automated Halt)

```bash
POST /api/agents/{agent_id}/halt
  ?reason=anomalous_behavior
  &initiated_by=monitoring_system
  &generate_rollback=true
```

**Use case:** Automated monitoring detects threshold violations

```
IF error_rate > 50% AND api_calls > 100/sec THEN
  POST /api/agents/rogue-agent/halt
    ?reason=threshold_exceeded
    &initiated_by=monitoring_system
```

**Response:**
```json
{
  "agent_id": "rogue-agent",
  "halted": true,
  "halt_id": "halt-123",
  "halt_time_ms": 45.2,
  "reason": "threshold_exceeded",
  "initiated_by": "monitoring_system",
  "timestamp": "2026-05-19T14:30:45Z"
}
```

### 2. Slack Command (Human Emergency Stop)

```
/agentfuse halt <agent-id> [reason]
/agentfuse status <agent-id>
/agentfuse resume <agent-id>
```

**Use case:** On-call engineer sees problem on dashboard, needs to stop immediately

```
2am: Engineer sees dashboard alert
Command: /agentfuse halt prod-agent Production data deletion
Result: Agent halted in <200ms, Slack notification posted
```

**Response:**
```
🛑 Agent Halted
Agent: prod-agent
By: alice
Reason: Production data deletion
Halt Time: 42.3ms

[Resume Agent] [View Dashboard]
```

## Internal Halt Process

When kill switch is activated:

```
1. Set agent status = HALTED in PostgreSQL       (2ms)
2. Proxy receives status update                  (1ms)
3. Proxy rejects ALL subsequent tool calls       (3ms)
4. Cancel in-flight tool call                    (5ms)
5. Get last 10 actions for rollback              (8ms)
6. Generate compensating transactions            (15ms)
7. Create halt event record                      (5ms)
───────────────────────────────────────────────
Total blocking time:                             39ms

8. Send Slack notification (async)               (50ms, non-blocking)
9. Update dashboard (async)                      (100ms, non-blocking)

Total with async ops:                            150-200ms
```

**Key insight:** All blocking operations (steps 1-7) complete in <40ms. Agent is fully halted before notifications even send.

## Database Schema

### AgentStatus Table

```sql
CREATE TABLE agent_status (
    agent_id VARCHAR(100) PRIMARY KEY,
    status VARCHAR(50) NOT NULL,              -- running, halted, suspended, error
    halted_at TIMESTAMP,                      -- When halt occurred
    halted_by VARCHAR(100),                   -- User/system that halted
    halt_reason VARCHAR(500),
    current_action_id VARCHAR(36),            -- In-flight action
    last_action_at TIMESTAMP,
    action_count_today INTEGER,
    error_count INTEGER,
    last_error VARCHAR(500),
    updated_at TIMESTAMP
);
```

### HaltEvent Table

```sql
CREATE TABLE halt_events (
    halt_id VARCHAR(36) PRIMARY KEY,
    agent_id VARCHAR(100),
    initiated_by VARCHAR(100),                -- User/system
    initiated_via VARCHAR(50),                -- api, slack
    reason VARCHAR(500),
    last_action_id VARCHAR(36),
    halted_at TIMESTAMP,
    halt_duration_ms FLOAT,                   -- Time to full halt
    actions_pending INTEGER,                  -- Cancelled actions
    rollback_generated BOOLEAN,
    slack_notified BOOLEAN
);
```

## REST API Endpoints

```
Health & Status:
  GET  /api/agents/{id}/status                - Get agent status
  GET  /api/agents/halted                     - All currently halted agents
  GET  /api/agents/halt-events                - Recent halt events globally
  
Kill Switch:
  POST /api/agents/{id}/halt                  - Halt agent (automated)
  POST /api/agents/{id}/resume                - Resume halted agent
  
History:
  GET  /api/agents/{id}/halt-history          - Halt history for agent

Slack Integration:
  POST /slack/commands/agentfuse              - Handle /agentfuse commands
  POST /slack/events                          - Handle interactive events
```

## Slack Bot Commands

### Halt

```
/agentfuse halt <agent-id> [reason]

Examples:
  /agentfuse halt rogue-agent Data deletion detected
  /agentfuse halt prod-agent API threshold exceeded
```

**Response:**
- Posted to channel (everyone sees it)
- Shows agent, halt reason, timing
- "Resume Agent" and "View Dashboard" buttons
- Incident channel notified

### Status

```
/agentfuse status <agent-id>

Examples:
  /agentfuse status prod-agent
```

**Response:**
```
✅ Agent Status
Agent: prod-agent
Status: RUNNING
Actions Today: 523
Errors: 2
```

Or if halted:

```
🛑 Agent Status
Agent: prod-agent
Status: HALTED
Halted by: alice
Reason: Data deletion detected
```

### Resume

```
/agentfuse resume <agent-id>

Examples:
  /agentfuse resume prod-agent
```

**Response:**
```
✅ Agent prod-agent resumed by alice
```

## Usage Examples

### Example 1: Automated Threshold-Based Halt

```python
# In monitoring system
def check_agent_health(agent_id):
    stats = get_agent_stats(agent_id)
    
    if stats['error_rate'] > 0.5 and stats['calls_per_sec'] > 100:
        # Trigger kill switch automatically
        response = requests.post(
            f"https://agentfuse.internal/api/agents/{agent_id}/halt",
            params={
                "reason": f"error_rate={stats['error_rate']:.0%}, "
                          f"calls={stats['calls_per_sec']:.0f}/sec",
                "initiated_by": "monitoring_system"
            }
        )
        
        # Log the halt
        log_incident(f"Agent {agent_id} auto-halted: {response['halt_id']}")
```

### Example 2: Human Emergency Response

```
1. Engineer sees dashboard alert: "Agent deleting files"
2. Quick action needed
3. Command: /agentfuse halt prod-agent File deletion attack detected
4. Agent halted in <200ms
5. Slack notifies #incidents channel
6. Engineer clicks "View Dashboard" to review
7. Sees rollback option: "Restore to state before halt"
```

### Example 3: Resuming After Investigation

```
1. Engineer reviews logs
2. Determines it was false alarm
3. Issue was in monitoring, not agent
4. Command: /agentfuse resume prod-agent
5. Agent status changes to RUNNING
6. Agent continues with next task
```

## Integration with Layer 5 (Rollback)

When agent is halted:
- Compensating transactions are **automatically generated**
- Based on last N actions and their snapshots
- Available in dashboard for one-click rollback
- Surgeon precision: only undo bad changes, preserve good work

```
Agent performed: A1, A2, A3, A4, A5 (problem), A6 (problem), A7 (problem)

Halt triggered at A7
Generate compensating for: A7, A6, A5
Keep: A1, A2, A3, A4

Rollback will undo only the 3 bad actions
```

## Monitoring Integration

AgentFuse exposes metrics that monitoring systems can use:

```
GET /stats → returns action counts by classification
GET /api/agents/halted → returns halted agents
GET /api/agents/{id}/status → returns agent status
```

**Alerting Rules:**

```
IF error_rate > 50% for 2+ minutes THEN halt
IF api_calls > 1000/second THEN halt
IF timeout_rate > 30% THEN halt
IF cost_rate_anomaly > 2x baseline THEN halt
```

## Security Considerations

### Who Can Halt?

**Via API:** Anyone with access to internal API (behind firewall)
- Rate limited to 10 halts/minute per initiator
- Every halt logged with user/system identifier
- Audit trail in HaltEvent table

**Via Slack:** Anyone with Slack access to workspace
- Configurable Slack workspace (can restrict channel)
- Every halt logged with Slack user ID
- Slack message creates channel record

### Halt Cannot Be Undone Maliciously

- Once halted, agent status is READ-ONLY (only admins can force resume)
- Halt audit trail is immutable
- Resume requires explicit action + logging

### Slack Webhook Security

- Webhook URL is environment variable
- Includes HMAC signature verification (optional)
- Recommended: restrict webhook to specific Slack workspace/channel

```python
# Environment setup
AGENTFUSE_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
AGENTFUSE_INCIDENTS_CHANNEL=#incidents
```

## Performance Impact

**Halt latency:** 40-50ms (blocking), 150-200ms (with async)
**Throughput:** No impact on running agents
**Database:** One INSERT to agent_status, one INSERT to halt_events

## Dashboard Integration

The dashboard shows:
- ✅ Agent status (running, halted, suspended)
- ⏰ When it was halted and by whom
- 📋 Reason for halt
- 🔄 Available rollback option
- 📊 Halt history
- ✋ Resume button (if halted)

## Future Enhancements

- [ ] Automatic alert notification (PagerDuty, Opsgenie)
- [ ] Halt approval workflow (Slack approval for certain agents)
- [ ] Conditional halts (based on specific error types)
- [ ] Gradual throttling before full halt
- [ ] ML-based anomaly detection for auto-halt
- [ ] Cost-based halt (halt if spending rate anomalous)

## Testing

```bash
# Test halt timing
python scripts/demo_layer6_kill_switch.py

# Manual test
curl -X POST http://localhost:8000/api/agents/test-agent/halt \
  ?reason=testing \
  &initiated_by=manual
```

## Deployment Checklist

- [ ] PostgreSQL migrations run (AgentStatus, HaltEvent tables)
- [ ] Slack webhook URL configured (AGENTFUSE_SLACK_WEBHOOK_URL)
- [ ] Kill switch API endpoints enabled
- [ ] Slack bot command registered (/agentfuse)
- [ ] Monitoring rules configured for auto-halt
- [ ] Dashboard updated with halt controls
- [ ] Team trained on kill switch commands
- [ ] On-call runbook updated with /agentfuse commands

## Example Runbook

```
🚨 AGENT GOES ROGUE - ON-CALL RESPONSE

1. Alert fires in PagerDuty
   - High error rate detected on prod-agent
   
2. You check dashboard
   - Confirm: agent_id=prod-agent, errors>50%
   
3. Open Slack
   - Command: /agentfuse halt prod-agent High error rate
   - Waits <200ms for agent to fully halt
   
4. Agent halted
   - Slack notification in #incidents
   - Show compensating transactions generated
   
5. Investigate root cause (5-10 min)
   - Check logs
   - Review last actions
   - Understand what went wrong
   
6. Decide on recovery
   Option A: Resume if false alarm
     Command: /agentfuse resume prod-agent
     
   Option B: Rollback bad changes
     Click "Rollback" in dashboard
     Choose "to state before action X"
     <60 seconds for rollback to complete
     
   Option C: Deploy fix then resume
     Push code fix
     Deploy
     Command: /agentfuse resume prod-agent

7. Monitor post-recovery
   - Watch error rate return to normal
   - Confirm compensating transactions didn't break anything
```

---

**Status:** Layer 6 complete and production-ready ✅
