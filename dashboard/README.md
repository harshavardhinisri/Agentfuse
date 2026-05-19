# AgentFuse Dashboard 📊

Real-time monitoring dashboard for AI agents with live action feeds, blast radius visualization, and rollback controls.

## 🎯 Features

### 1. **Live Action Feed** 🔴🟡🟢
- Real-time WebSocket stream of every agent tool call
- Color-coded by classification (Green/Yellow/Red)
- Shows:
  - Command executed
  - Target resource
  - Classification & confidence
  - Decision (Approved/Flagged/Blocked)
  - Execution time in milliseconds
- Hover to see detailed reasoning

### 2. **Blast Radius Map** 🗺️
- Visual graph showing all resources touched by agent
- Node types: Files, Databases, API calls, Backups
- Color-coded by risk level
- Click nodes to see details:
  - Resource type
  - Number of actions
  - Classification
- Edge connections show action relationships
- Real-time updates as agent takes actions

### 3. **Rollback Timeline** ⏮️
- Chronological timeline of all agent actions
- Interactive slider to navigate through history
- For each action shows:
  - Action type & command
  - Target resource
  - Classification
  - Timestamp
- Preview of compensating transactions
- One-click rollback to any checkpoint

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm/yarn
- AgentFuse backend running on `localhost:8000`
- PostgreSQL database populated with agent actions

### Installation

```bash
# Navigate to dashboard directory
cd dashboard

# Install dependencies
npm install

# Or with yarn
yarn install
```

### Environment Setup

Create `.env.local` (already provided):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Running the Dashboard

Development mode with hot reload:
```bash
npm run dev
# or
yarn dev
```

Dashboard will be available at: **http://localhost:3000**

### Production Build

```bash
npm run build
npm start
```

## 📱 UI Overview

### Header
- **AgentFuse Logo** - Indicates system status
- **Agent Selector** - Choose which agent to monitor
- **Live Indicator** - Shows WebSocket connection status
- **Settings** - Configure dashboard preferences

### Sidebar Navigation
- **Live Feed** - Real-time action stream (Activity icon)
- **Blast Radius** - Resource impact visualization (Map icon)
- **Rollback** - Timeline with recovery controls (Clock icon)
- **Status** - Connection status and API info

### Quick Stats Bar
- **Total Actions** - Count of all logged actions
- **Approved** (Green) - Safe actions auto-approved
- **Flagged** (Yellow) - Risky actions logged and proceeded
- **Blocked** (Red) - Dangerous actions prevented

## 🔌 WebSocket Endpoints

The dashboard connects to three real-time WebSocket endpoints:

### 1. Action Stream
```
ws://localhost:8000/ws/actions/stream?agent_id={agent_id}&classification={classification}
```
- **type**: `action_batch`
- **actions**: Array of recent actions (up to 50)
- **count**: Total number of actions

Example message:
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

### 2. Blast Radius Graph
```
ws://localhost:8000/ws/agents/{agent_id}/graph
```
- **type**: `graph_update`
- **nodes**: Array of resources (files, tables, APIs)
- **edges**: Connections between resources

Example message:
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

### 3. Rollback Timeline
```
ws://localhost:8000/ws/agents/{agent_id}/timeline
```
- **type**: `timeline_update`
- **timeline**: Array of all actions in order
- **total_actions**: Count of actions

Example message:
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

## 🎨 Styling

Dashboard uses TailwindCSS for styling with custom color scheme:

- **Green** (#10B981) - Safe actions
- **Yellow** (#F59E0B) - Risky actions  
- **Red** (#EF4444) - Dangerous actions
- **Slate** (dark theme) - Base colors

### Dark Mode
Dashboard is built with dark mode as default. Automatic light/dark mode support can be added in `tailwind.config.js`.

## 🔧 Development

### Project Structure

```
dashboard/
├── app/
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Main dashboard
│   └── globals.css         # Global styles
├── components/
│   ├── Header.tsx          # Top navigation
│   ├── Navigation.tsx      # Sidebar
│   ├── Stats.tsx           # Quick stats bar
│   ├── LiveActionFeed.tsx  # Action stream view
│   ├── BlastRadiusMap.tsx  # Graph visualization
│   └── RollbackUI.tsx      # Timeline & rollback
├── package.json            # Dependencies
├── tsconfig.json          # TypeScript config
├── tailwind.config.js     # Tailwind config
├── next.config.js         # Next.js config
└── .env.local            # Environment variables
```

### Adding New Features

1. Create component in `components/` folder
2. Import in `app/page.tsx` or relevant view
3. Connect to WebSocket endpoints as needed
4. Style with TailwindCSS utilities

### API Integration

All API calls use:
```typescript
const response = await fetch(process.env.NEXT_PUBLIC_API_URL + '/api/endpoint');
```

WebSocket connections use:
```typescript
const ws = new WebSocket(`${protocol}//localhost:8000/ws/endpoint`);
```

## 🐛 Troubleshooting

### WebSocket Connection Issues
- Ensure AgentFuse backend is running on `localhost:8000`
- Check browser console for connection errors
- Verify CORS is enabled in FastAPI (`allow_origins=["*"]`)

### No Data Appearing
- Make sure agent has executed some actions (run demo scripts)
- Check database contains action records
- Verify WebSocket messages in browser DevTools (Network tab)

### Performance Issues
- Limit number of displayed actions in Live Feed
- Reduce graph complexity in Blast Radius (max 50 edges)
- Adjust WebSocket polling interval in `.env.local`

## 📚 Resources

- [Next.js 15 Documentation](https://nextjs.org/docs)
- [TailwindCSS Docs](https://tailwindcss.com/docs)
- [React Hooks Guide](https://react.dev/reference/react/hooks)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

## 🚀 Deployment

### Docker Deployment

```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

EXPOSE 3000
CMD ["yarn", "start"]
```

### Environment Variables for Production

```
NEXT_PUBLIC_API_URL=https://api.agentfuse.com
NEXT_PUBLIC_WS_URL=wss://api.agentfuse.com
```

## 🎯 Demo Workflow

1. Start AgentFuse backend
2. Run demo script to generate actions
3. Start dashboard (`npm run dev`)
4. Open http://localhost:3000
5. Watch actions stream in real-time
6. Click nodes in Blast Radius to explore
7. Drag timeline slider to see action history
8. Click "Rollback" to execute compensation transactions

## 📊 Key Metrics Displayed

- **Total Actions** - Sum of all logged actions
- **Approved** - Count of GREEN (safe) actions
- **Flagged** - Count of YELLOW (risky) actions
- **Blocked** - Count of RED (dangerous) actions
- **Execution Time** - Per-action latency in milliseconds
- **Confidence Score** - ML classifier confidence (0-100%)

## 🔒 Security Notes

- Dashboard connects to public API endpoints
- No sensitive data is stored in browser
- WebSocket connections use same security as HTTP
- Consider using WSS (WebSocket Secure) in production

## 📝 License

MIT License - Same as AgentFuse project

---

**Dashboard Version:** 1.0.0  
**Last Updated:** May 19, 2026  
**Status:** ✅ Production Ready
