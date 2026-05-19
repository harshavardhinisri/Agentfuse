# 🎯 AgentFuse Full Stack Setup & Demo

Complete guide to run the backend, generate demo data, and launch the interactive dashboard.

## 📋 Prerequisites

- **Backend**: Python 3.9+, PostgreSQL 15+, FastAPI
- **Frontend**: Node.js 18+, npm/yarn
- **Ports**: 8000 (API), 5432 (PostgreSQL), 3000 (Dashboard)

---

## 🚀 Step 1: Start the Backend

### 1a. Using Docker (Recommended)

```bash
cd /Users/harsha/projects/Agentfuse

# Start PostgreSQL + AgentFuse API
docker-compose up -d

# Verify both are running
docker-compose ps

# Check API health
curl http://localhost:8000/health
```

### 1b. Using Local PostgreSQL

```bash
# Start PostgreSQL
brew services start postgresql

# Create database
createdb agentfuse

# Activate Python venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Initialize database
python -c "from src.database import get_db_manager; get_db_manager().init_db()"

# Start server
python -m src.main
```

**Verify Backend is Running:**
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}

curl http://localhost:8000/api/stats
# Should return: {"total_actions_logged": 0, ...}
```

---

## 📊 Step 2: Generate Demo Data

Run demo scripts to populate the database with sample actions:

```bash
cd /Users/harsha/projects/Agentfuse

# Activate venv (if not already)
source venv/bin/activate

# Run comprehensive demo
python scripts/demo.py

# Optional: Run specific layer demos
python scripts/demo_layer6_kill_switch.py
python scripts/demo_layers_3_4_5.py
```

**Expected Output:**
```
AGENTFUSE DEMO - Agent Safety Layer

Demo 1: Safe Read - Get application logs
Classification: GREEN (95% confidence)
Decision: APPROVED

Demo 3: DANGEROUS - Delete production database
Classification: RED (99% confidence)  
Decision: BLOCKED 🚫

Proxy Statistics
Total Calls: 8
Approved: 3 (37%)
Flagged: 2 (25%)
Blocked: 3 (37%)
```

**Check Database:**
```bash
# Connect to PostgreSQL
psql agentfuse

# Count logged actions
SELECT COUNT(*) FROM actions;

# See recent actions
SELECT agent_id, action_type, classification, decision 
FROM actions 
ORDER BY created_at DESC 
LIMIT 10;

# Exit
\q
```

---

## 🎨 Step 3: Start the Dashboard

### 3a. Install Dashboard Dependencies

```bash
cd /Users/harsha/projects/Agentfuse/dashboard

# Install Node.js dependencies
npm install

# Or with yarn
yarn install
```

### 3b. Start Development Server

```bash
# From dashboard directory
npm run dev

# Dashboard will start on http://localhost:3000
# Watch for: "ready - started server on 0.0.0.0:3000"
```

### 3c. Open Dashboard in Browser

Visit: **http://localhost:3000**

You should see:
- Header with agent selector and status
- Sidebar with three views
- Quick stats showing action counts
- Three main panels:
  - 🔴 **Live Action Feed** - Real-time stream
  - 🗺️ **Blast Radius Map** - Resource graph
  - ⏮️ **Rollback Timeline** - Action history

---

## 🎮 Demo Workflow

### 1. View Live Actions
- Navigate to **Live Feed** tab
- See each action with:
  - Command executed
  - Classification (🟢 Green / 🟡 Yellow / 🔴 Red)
  - Decision (Approved/Flagged/Blocked)
  - Confidence percentage
  - Execution time
- Hover over actions to see reasoning

### 2. Explore Blast Radius
- Go to **Blast Radius** tab
- See visual graph of resources touched by agent
- Node types:
  - 📄 Files
  - 🗄️ Databases
  - 🌐 API Calls
  - 💾 Backups
- Click nodes to see:
  - Resource type and path
  - Number of actions on that resource
  - Risk classification
- Use filter dropdown to show specific resource types

### 3. Plan & Execute Rollback
- Open **Rollback** tab
- See complete timeline of actions
- **Interactive Slider:**
  - Drag to any point in time
  - See preview of what will be rolled back
  - Number of compensating transactions shown
- Click **"Rollback to Checkpoint"** to:
  - Execute compensating transactions
  - Undo changes from that point forward
  - Return to safe state

### 4. Switch Agents
- Use **Agent Selector** in header
- Choose from:
  - 🤖 Claude Dev
  - ⚙️ Claude Prod  
  - 🦾 Automation Bot
  - 🧪 Test Agent
- Dashboard updates all three views for new agent

### 5. Monitor in Real-Time
- Run more demo actions: `python scripts/demo.py`
- Watch Live Feed update in real-time via WebSocket
- See Blast Radius expand as agent touches new resources
- Timeline updates as new actions are logged

---

## 📊 Full Stack Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  Browser (Port 3000)                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │        Next.js 15 Dashboard (React Frontend)          │ │
│  │  ┌──────────────┬──────────────┬──────────────┐        │ │
│  │  │  Live Feed   │ Blast Radius │   Rollback   │        │ │
│  │  │  (Actions)   │   (Graph)    │  (Timeline)  │        │ │
│  │  └──────────────┴──────────────┴──────────────┘        │ │
│  └────────────────────────────────────────────────────────┘ │
│                             ▲                                │
│        ┌────────────────────┼────────────────────┐          │
│        │                    │                    │          │
│    HTTP REST API      WebSocket Streams (Real-Time)         │
│        │                    │                    │          │
└────────┼────────────────────┼────────────────────┘          │
         │                    │                    
┌────────▼────────────────────▼────────────────────┐          
│        FastAPI Backend (Port 8000)               │
│  ┌─────────────────────────────────────────────┐ │
│  │  Layer 1: MCP Proxy (Interception)         │ │
│  │  Layer 2: DeBERTa Classifier (ML)          │ │
│  │  Layer 3: Scope Rules (Deterministic)      │ │
│  │  Layer 4: Snapshots (Before-State)         │ │
│  │  Layer 5: Rollback (Compensating Txs)      │ │
│  │  Layer 6: Kill Switch (Emergency Halt)     │ │
│  │                                             │ │
│  │  REST API Endpoints (18 total)             │ │
│  │  WebSocket Endpoints (3 streams)           │ │
│  └─────────────────────────────────────────────┘ │
└────────┬─────────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────┐
│  PostgreSQL Database (Port 5432)                  │
│  ┌─────────────────────────────────────────────┐ │
│  │  9 Tables:                                  │ │
│  │  • actions (all logged actions)             │ │
│  │  • blocked_actions (prevented actions)      │ │
│  │  • alert_logs (security alerts)             │ │
│  │  • agent_policies (per-agent config)        │ │
│  │  • scope_rules (safety rules)               │ │
│  │  • snapshots (before-state captures)        │ │
│  │  • rollbacks (recovery transactions)        │ │
│  │  • agent_status (current state)             │ │
│  │  • halt_events (kill switch log)            │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 🔌 WebSocket Real-Time Flow

```
Dashboard (Browser)
    │
    ├─ ws://localhost:8000/ws/actions/stream?agent_id=claude-dev
    │  └─ Receives: Action batches every 500ms
    │     • action_id, command, classification, decision, timestamp
    │
    ├─ ws://localhost:8000/ws/agents/claude-dev/graph
    │  └─ Receives: Graph updates every 1s
    │     • nodes (resources), edges (relationships)
    │
    └─ ws://localhost:8000/ws/agents/claude-dev/timeline
       └─ Receives: Timeline updates every 1s
          • all actions in chronological order
          • rollback options
```

---

## 🛠️ Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
PORT=8001 python -m src.main
```

**Database connection error:**
```bash
# Check PostgreSQL is running
brew services list

# Start if needed
brew services start postgresql

# Verify connection
psql agentfuse
```

**No actions in dashboard:**
```bash
# Generate demo data
python scripts/demo.py

# Check database has data
psql agentfuse -c "SELECT COUNT(*) FROM actions;"
```

### Dashboard Issues

**Cannot connect to localhost:3000:**
```bash
# Check if Next.js is running
lsof -i :3000

# Start dashboard if needed
cd dashboard && npm run dev
```

**WebSocket connection refused:**
- Verify backend is running: `curl http://localhost:8000/health`
- Check CORS is enabled (it is by default)
- Look at browser console (F12 → Network → WS tab)

**No WebSocket messages:**
- Ensure demo data was generated
- Check browser DevTools → Network → WS
- Verify message is "action_batch", "graph_update", or "timeline_update"

**Styles not loading:**
```bash
# Rebuild Tailwind
cd dashboard && npm run build

# Or clear Next.js cache
rm -rf .next && npm run dev
```

---

## 📈 Monitoring the Demo

### Terminal 1: Backend Server
```bash
# Watch logs
cd /Users/harsha/projects/Agentfuse
source venv/bin/activate
python -m src.main
```

### Terminal 2: Dashboard
```bash
cd dashboard
npm run dev
# Logs show WebSocket connections
```

### Terminal 3: Run Demo
```bash
cd /Users/harsha/projects/Agentfuse
source venv/bin/activate

# Option A: Run full demo once
python scripts/demo.py

# Option B: Run continuously (for live demo)
while true; do
  python scripts/demo.py
  sleep 2
done
```

---

## 🎬 Live Demo Script

Perfect sequence for impressive demo:

```bash
# Terminal 1: Start backend
cd /Users/harsha/projects/Agentfuse
docker-compose up -d  # or: python -m src.main

# Wait 5 seconds for startup

# Terminal 2: Start dashboard
cd dashboard
npm run dev

# Open browser: http://localhost:3000

# Terminal 3: Generate demo data continuously
cd /Users/harsha/projects/Agentfuse
while true; do
  python scripts/demo.py
  sleep 3
done
```

Then show:
1. **Live Feed** - Actions streaming in real-time
2. **Blast Radius** - Resources expanding as agent acts
3. **Rollback** - Slide timeline and preview recovery
4. **Kill Switch** - Execute a rollback to safe state

---

## 🔐 Security Notes for Demo

- Dashboard is accessible from `localhost:3000` only
- API is on `localhost:8000` (change for production)
- WebSocket uses unsecured `ws://` (use `wss://` in production)
- No authentication enabled (add JWT for production)

---

## 📦 Project Files

**Backend:**
- `src/main.py` - FastAPI application
- `src/api/websocket.py` - WebSocket endpoints (NEW)
- `src/layers/` - 6 layers of defense
- `scripts/demo*.py` - Demo generators

**Frontend:**
- `dashboard/app/page.tsx` - Main page
- `dashboard/components/LiveActionFeed.tsx` - Action stream
- `dashboard/components/BlastRadiusMap.tsx` - Graph view
- `dashboard/components/RollbackUI.tsx` - Timeline slider
- `dashboard/package.json` - Dependencies

**Database:**
- `docker-compose.yml` - PostgreSQL container
- `src/database.py` - Schema definition

---

## ✅ Demo Readiness Checklist

- [ ] Docker running (or PostgreSQL started)
- [ ] Backend health check passing
- [ ] Demo data generated (actions in database)
- [ ] Dashboard installed and running
- [ ] Browser showing 3 views with live data
- [ ] WebSocket connections active (Network tab)
- [ ] Can drag timeline slider
- [ ] Can click nodes in blast radius
- [ ] Rollback button functional

---

## 🎓 What You'll Learn

1. **Real-Time Monitoring** - WebSocket streaming architecture
2. **Agent Safety** - 6 layers of AI agent control
3. **UI/UX Design** - Real-time dashboard patterns
4. **Full Stack Development** - Python backend + React frontend
5. **Database Design** - Audit logging with 9 tables
6. **Recovery Patterns** - Rollback with compensating transactions

---

## 🚀 Next Steps

After demo runs successfully:

1. **Customize Policies** - Edit `config/policies.yaml`
2. **Add More Agents** - Extend agent selector
3. **Deploy to Production** - Use Docker + AWS
4. **Integrate with Real Agents** - Claude, Cursor, etc.
5. **Add Slack Alerts** - Use existing kill switch commands
6. **Monitor with Prometheus** - Add metrics collection

---

**Status:** ✅ Ready to Demo  
**Last Updated:** May 19, 2026  
**Version:** 1.0.0
