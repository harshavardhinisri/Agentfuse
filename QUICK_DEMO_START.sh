#!/bin/bash

# AgentFuse Full Stack Demo - One-Command Start
# Run this script to start everything and launch the demo

set -e

AGENTFUSE_DIR="/Users/harsha/projects/Agentfuse"
DASHBOARD_DIR="$AGENTFUSE_DIR/dashboard"

echo "🚀 AgentFuse Full Stack Demo Launcher"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Start Backend
echo -e "${BLUE}Step 1: Starting Backend...${NC}"
cd "$AGENTFUSE_DIR"

# Check if using Docker or local setup
if command -v docker-compose &> /dev/null; then
    echo "Starting PostgreSQL + API with Docker..."
    docker-compose up -d
    echo -e "${GREEN}✓ Backend started${NC}"
    sleep 3
else
    echo "Docker not found, assuming local PostgreSQL is running..."
    if ! brew services list | grep -q "postgresql.*started"; then
        echo "Starting PostgreSQL..."
        brew services start postgresql
    fi
fi

# Wait for API to be ready
echo "Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo -e "${GREEN}✓ API is ready${NC}"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 1
done

# Step 2: Generate Demo Data
echo ""
echo -e "${BLUE}Step 2: Generating Demo Data...${NC}"

# Activate venv
if [ ! -d "venv" ]; then
    echo "Creating Python venv..."
    python3 -m venv venv
fi

source venv/bin/activate

# Check dependencies
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip install -e ".[dev]" > /dev/null
fi

# Run demo
echo "Running demo scenarios..."
python scripts/demo.py > /dev/null 2>&1 || true
echo -e "${GREEN}✓ Demo data generated${NC}"

# Step 3: Start Dashboard
echo ""
echo -e "${BLUE}Step 3: Starting Dashboard...${NC}"
cd "$DASHBOARD_DIR"

if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install --silent
fi

echo -e "${GREEN}✓ Dashboard dependencies ready${NC}"

# Step 4: Summary
echo ""
echo "======================================"
echo -e "${GREEN}✓ All systems ready!${NC}"
echo "======================================"
echo ""
echo "📊 Dashboard:"
echo -e "${BLUE}  http://localhost:3000${NC}"
echo ""
echo "🔌 API:"
echo -e "${BLUE}  http://localhost:8000${NC}"
echo ""
echo "📚 API Docs:"
echo -e "${BLUE}  http://localhost:8000/docs${NC}"
echo ""
echo "Starting dashboard in development mode..."
echo "Press Ctrl+C to stop"
echo ""

# Start dashboard
npm run dev
