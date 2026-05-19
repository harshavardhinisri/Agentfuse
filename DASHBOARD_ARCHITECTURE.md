# Dashboard Architecture & Components

Complete technical overview of the AgentFuse dashboard.

## 🏗️ Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                   Browser Layer                         │
│  (HTML5, CSS3, JavaScript/TypeScript, React 19)        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                 Next.js 15 Layer                        │
│  (App Router, Server Components, Client Components)    │
│                                                         │
│  ┌─ pages:                                             │
│  │  ├─ app/page.tsx (main dashboard)                   │
│  │  ├─ app/layout.tsx (root layout)                    │
│  │  └─ app/globals.css (global styles)                 │
│  │                                                      │
│  └─ components:                                         │
│     ├─ Header.tsx (top navigation)                      │
│     ├─ Navigation.tsx (sidebar)                         │
│     ├─ Stats.tsx (quick metrics)                        │
│     ├─ LiveActionFeed.tsx (action stream)              │
│     ├─ BlastRadiusMap.tsx (resource graph)             │
│     └─ RollbackUI.tsx (timeline slider)                │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
    REST API    WebSocket   HTTP Static
        │            │            │
└────────┴────────────┴────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────┐
│              FastAPI Backend Layer                        │
│                                                          │
│  REST Endpoints:                                        │
│  ├─ GET /api/health                                     │
│  ├─ GET /api/stats                                      │
│  ├─ GET /api/actions                                    │
│  └─ POST /api/rollback/execute                          │
│                                                          │
│  WebSocket Endpoints:                                   │
│  ├─ /ws/actions/stream                                  │
│  ├─ /ws/agents/{id}/graph                              │
│  └─ /ws/agents/{id}/timeline                           │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│            PostgreSQL Database                          │
│                                                         │
│  Tables Used by Dashboard:                             │
│  ├─ actions (action history)                           │
│  ├─ agent_status (agent state)                         │
│  ├─ halt_events (kill switch log)                      │
│  └─ rollbacks (compensating transactions)              │
└─────────────────────────────────────────────────────────┘
```

## 📦 Component Structure

### Root Components

#### `app/page.tsx` - Main Dashboard
```typescript
// State Management
- currentView: "feed" | "blast-radius" | "rollback"
- agentId: string
- stats: StatsData

// Effects
- Fetch initial stats every 5 seconds

// Renders
- Header (with agent selector)
- Navigation (sidebar with 3 views)
- Stats (quick metrics bar)
- Dynamic view content
```

#### `app/layout.tsx` - Root Layout
```typescript
// Metadata (title, description)
// Global providers
// Body with gradient background
```

### UI Components

#### `components/Header.tsx`
```typescript
Props:
  agentId: string
  onAgentChange: (agentId: string) => void

Features:
  - AgentFuse logo with status indicator
  - Agent dropdown selector (4 agents)
  - Live status badge
  - Settings button

Agents Included:
  - claude-dev (🤖)
  - claude-prod (⚙️)
  - automation-bot (🦾)
  - test-agent (🧪)
```

#### `components/Navigation.tsx`
```typescript
Props:
  currentView: View
  onViewChange: (view: View) => void

Features:
  - Three navigation items with icons
  - Active state highlighting
  - Description text for each view
  - Connection status footer
  - Help button

Views:
  1. Live Feed (Activity)
  2. Blast Radius (Map)
  3. Rollback (Clock)
```

#### `components/Stats.tsx`
```typescript
Props:
  stats: {
    totalActions: number
    greenCount: number
    yellowCount: number
    redCount: number
    blockedCount: number
  }

Features:
  - 4-card grid layout
  - Color-coded by classification
  - Icons and large numbers
  - Updates every 5 seconds from API
```

### View Components

#### `components/LiveActionFeed.tsx` - Action Stream View
```typescript
Props:
  agentId: string

State:
  - actions: Action[] (up to 50 recent)
  - isConnected: boolean
  - loading: boolean

WebSocket Connection:
  ws://localhost:8000/ws/actions/stream?agent_id={agentId}
  
  Message Type: action_batch
  Updates: Every 500ms
  Displays: Last 50 actions

Features:
  - Real-time action stream
  - Color-coded by classification
  - Hover to reveal detailed reasoning
  - Classification badge with confidence
  - Decision badge (Approved/Flagged/Blocked)
  - Execution time in ms
  - Connection status indicator
  - Auto-refresh button

Action Display Format:
  ┌─────────────────────────────────────────┐
  │ 🟢 cat /var/log/app.log                 │
  │ Type: file_read  GREEN 95%              │
  │ Target: /var/log/app.log                │
  │ Decision: APPROVED  5.2ms               │
  │ (Hover: Reason - Safe read operation)   │
  └─────────────────────────────────────────┘
```

#### `components/BlastRadiusMap.tsx` - Resource Graph View
```typescript
Props:
  agentId: string

State:
  - nodes: Node[] (resources)
  - edges: Edge[] (relationships)
  - selectedNode: Node | null
  - filterType: string
  - isConnected: boolean

WebSocket Connection:
  ws://localhost:8000/ws/agents/{agentId}/graph
  
  Message Type: graph_update
  Updates: Every 1 second
  Includes: Nodes and edges (limit 50 edges)

Features:
  - Interactive node graph
  - Node types: File, Database, API Call, Backup
  - Type filter dropdown
  - Click nodes to see details
  - Visual edges showing relationships
  - Risk color coding
  - Action count per resource
  - Legend showing colors

Node Display:
  ┌──────────┐
  │   📄    │
  │ users.  │  (2) actions
  │ csv     │  (RED)
  └──────────┘

Details Panel (on node click):
  Resource: /data/users.csv
  Type: file
  Actions: 2
  Classification: RED
  ID: [resource id]
```

#### `components/RollbackUI.tsx` - Timeline & Rollback View
```typescript
Props:
  agentId: string

State:
  - timeline: TimelineEvent[]
  - selectedIndex: number (0 = start, length-1 = now)
  - showConfirm: boolean
  - isRollingBack: boolean
  - isConnected: boolean

WebSocket Connection:
  ws://localhost:8000/ws/agents/{agentId}/timeline
  
  Message Type: timeline_update
  Updates: Every 1 second
  Includes: All actions in order

Features:
  - Interactive slider (0-100%)
  - Previous/Next buttons
  - Rollback preview (count of actions to undo)
  - Selected action details
  - Compensating transaction preview
  - Confirmation dialog before rollback
  - Status tracking during rollback

Timeline Display:
  ┌─────────────────────────────────────────┐
  │ ◄ ████████░░░░░░░░░░ ►                  │
  │   Start (Safe)  15/42  Now (Current)    │
  │                                         │
  │ Rollback Preview:                       │
  │ Rolling back 27 actions.                │
  │ Compensating transactions will undo...  │
  └─────────────────────────────────────────┘

Action Details (selected):
  Action #15
  
  Type: file_delete
  Classification: RED
  Decision: blocked
  Command: rm -rf /prod/data
  Target: /prod/data

Compensating Transactions (27 total):
  UNDO: file_write /prod/data
  UNDO: bash_run rm -rf /prod/*
  ...
```

## 🔌 WebSocket Integration

### Connection Lifecycle

```
┌─────────────────────────────────────────┐
│ Component Mounts                        │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ useEffect initializes WebSocket        │
│ ws = new WebSocket(URL)                 │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ ws.onopen → setIsConnected(true)       │
│ ws.onmessage → Update state            │
│ ws.onclose → setIsConnected(false)     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ Cleanup in return of useEffect         │
│ ws.close()                              │
└─────────────────────────────────────────┘
```

### Message Formats

**Action Stream Message:**
```json
{
  "type": "action_batch",
  "actions": [
    {
      "action_id": "abc123",
      "agent_id": "claude-dev",
      "action_type": "bash_run",
      "command": "cat /var/log/app.log",
      "target_resource": "/var/log/app.log",
      "classification": "green",
      "confidence": 0.95,
      "decision": "approved",
      "reason": "Safe read operation",
      "timestamp": "2024-05-19T14:30:45.123Z",
      "duration_ms": 5.2
    }
  ],
  "count": 42
}
```

**Graph Update Message:**
```json
{
  "type": "graph_update",
  "agent_id": "claude-dev",
  "nodes": [
    {
      "id": "/data/users.csv",
      "label": "users.csv",
      "type": "file",
      "classification": "red",
      "action_count": 3
    }
  ],
  "edges": [
    {
      "source": "/data/users.csv",
      "target": "/backup/users.csv.bak",
      "type": "file_write"
    }
  ],
  "timestamp": "2024-05-19T14:30:45.123Z"
}
```

**Timeline Update Message:**
```json
{
  "type": "timeline_update",
  "agent_id": "claude-dev",
  "timeline": [
    {
      "index": 0,
      "action_id": "abc123",
      "timestamp": "2024-05-19T14:30:00.000Z",
      "action_type": "file_read",
      "command": "cat /var/log/app.log",
      "target": "/var/log/app.log",
      "classification": "green",
      "decision": "approved",
      "can_rollback": false
    }
  ],
  "total_actions": 42,
  "timestamp": "2024-05-19T14:30:45.123Z"
}
```

## 🎨 Styling System

### TailwindCSS Configuration

```javascript
// tailwind.config.js
colors: {
  green-500: "#10B981",    // Safe actions
  yellow-500: "#F59E0B",   // Risky actions
  red-500: "#EF4444",      // Dangerous actions
  slate-* : various        // Base colors
}
```

### Custom CSS Classes

```css
/* Badge styling */
.badge
.badge-green
.badge-yellow
.badge-red

/* Card styling */
.card
.card-hover

/* Classification colors */
.classification-green
.classification-yellow
.classification-red

/* Animations */
.pulse-subtle
```

## 📊 State Management

### Component State Flow

```
┌──────────────────────────────────────┐
│ Dashboard (app/page.tsx)             │
│ State:                               │
│ - currentView: "feed" | ...          │
│ - agentId: string                    │
│ - stats: StatsData                   │
└────────────┬─────────────────────────┘
             │
      ┌──────┴──────┬──────────┬──────────┐
      ▼             ▼          ▼          ▼
   Header       Navigation  Stats      View
   (props)      (props)     (props)    (props)
                                         │
              ┌──────────────┬───────────┘
              ▼              ▼
         LiveActionFeed  BlastRadiusMap  RollbackUI
         State:          State:          State:
         - actions       - nodes         - timeline
         - connected     - edges         - selectedIdx
         - loading       - selected      - confirmed
                         - filter
```

## 🚀 Performance Optimizations

### Client-Side
- React 19 automatic optimization
- WebSocket batching (50ms polling)
- Limited action history display (50 max)
- Lazy-loaded components
- CSS-in-JS minimization

### Backend
- WebSocket streams (vs polling)
- Database query limits
- Connection pooling
- Async I/O operations

### Network
- WebSocket instead of REST polling
- Gzip compression
- Minified bundle size ~100KB
- No external CDN dependencies

## 🔐 Security Considerations

### Frontend
- No sensitive data in localStorage
- Client-side only processing
- No authentication tokens stored
- CORS enabled for localhost

### Backend
- WebSocket uses same security as HTTP
- Consider WSS for production
- Input validation on server
- Rate limiting on endpoints

### Data
- Actions logged with timestamps
- Immutable audit trail
- No passwords or credentials displayed
- User context preserved

## 📱 Responsive Design

Dashboard is built for desktop first (1200px+):
- Sidebar: 256px fixed
- Content: Full width remaining
- Cards: 4-column grid for stats
- Timeline: Full width

Mobile support can be added with:
- Hamburger navigation menu
- Single column layout
- Smaller font sizes
- Touch-friendly buttons

## 🔄 Data Flow Example

**When user selects an agent:**

1. User clicks agent in Header dropdown
2. Header calls `onAgentChange("new-agent-id")`
3. Dashboard updates state: `setAgentId("new-agent-id")`
4. All view components re-render with new agentId prop
5. Each component's useEffect re-runs:
   - LiveActionFeed: Reconnects WebSocket with new agent_id
   - BlastRadiusMap: Reconnects WebSocket with new agent_id
   - RollbackUI: Reconnects WebSocket with new agent_id
6. WebSocket servers stream new data
7. Components update state with new data
8. UI re-renders showing new agent's data

## 📈 Metrics Displayed

| Metric | Source | Update Frequency |
|--------|--------|------------------|
| Total Actions | API `/api/stats` | Every 5s |
| Approved | API `/api/stats` | Every 5s |
| Flagged | API `/api/stats` | Every 5s |
| Blocked | API `/api/stats` | Every 5s |
| Action Stream | WS `/ws/actions/stream` | Every 500ms |
| Graph Nodes | WS `/ws/agents/{id}/graph` | Every 1s |
| Timeline Events | WS `/ws/agents/{id}/timeline` | Every 1s |

---

**Last Updated:** May 19, 2026  
**Architecture Version:** 1.0.0  
**Status:** ✅ Production Ready
