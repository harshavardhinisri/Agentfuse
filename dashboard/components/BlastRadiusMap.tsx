"use client";

import { useState, useEffect } from "react";
import { Network, RefreshCw, Filter } from "lucide-react";

interface Node {
  id: string;
  label: string;
  type: string;
  classification: string;
  action_count: number;
}

interface Edge {
  source: string;
  target: string;
  type: string;
}

interface BlastRadiusMapProps {
  agentId: string;
}

export default function BlastRadiusMap({ agentId }: BlastRadiusMapProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [filterType, setFilterType] = useState<string>("all");

  useEffect(() => {
    // Connect WebSocket for real-time graph updates
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(
      `${protocol}//localhost:8000/ws/agents/${agentId}/graph`
    );

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "graph_update") {
          setNodes(data.nodes || []);
          setEdges(data.edges || []);
        }
      } catch (error) {
        console.error("Failed to parse graph data:", error);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [agentId]);

  const getNodeColor = (classification: string) => {
    switch (classification) {
      case "green":
        return "bg-green-500/20 border-green-500";
      case "yellow":
        return "bg-yellow-500/20 border-yellow-500";
      case "red":
        return "bg-red-500/20 border-red-500";
      default:
        return "bg-slate-600/20 border-slate-600";
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "file":
        return "📄";
      case "database":
        return "🗄️";
      case "api_call":
        return "🌐";
      case "backup":
        return "💾";
      default:
        return "📦";
    }
  };

  const filteredNodes =
    filterType === "all" ? nodes : nodes.filter((n) => n.type === filterType);

  const resourceTypes = ["all", ...new Set(nodes.map((n) => n.type))];

  // Calculate positions for nodes (simple grid layout)
  const getNodePosition = (index: number) => {
    const cols = 4;
    const row = Math.floor(index / cols);
    const col = index % cols;
    return {
      left: `${col * 25 + 12.5}%`,
      top: `${row * 25 + 20}%`,
    };
  };

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Blast Radius Map</h2>
          <p className="text-sm text-slate-400 mt-1">
            Visual graph of resources touched by agent
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm text-slate-50"
          >
            {resourceTypes.map((type) => (
              <option key={type} value={type}>
                {type === "all"
                  ? "All Resources"
                  : type.charAt(0).toUpperCase() + type.slice(1)}
              </option>
            ))}
          </select>
          <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors">
            <RefreshCw size={20} className="text-slate-400" />
          </button>
        </div>
      </div>

      {/* Graph Container */}
      <div className="flex-1 bg-slate-800/20 border border-slate-700 rounded-lg relative overflow-hidden">
        {!isConnected && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-slate-400">Connecting to WebSocket...</div>
          </div>
        )}

        {/* SVG Canvas for edges */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 10 3, 0 6" fill="#64748b" />
            </marker>
          </defs>
          {edges.map((edge, i) => {
            const sourceNode = nodes.find((n) => n.id === edge.source);
            const targetNode = nodes.find((n) => n.id === edge.target);
            if (!sourceNode || !targetNode) return null;

            return (
              <line
                key={i}
                x1={`calc(${getNodePosition(nodes.indexOf(sourceNode)).left} + 40px)`}
                y1={`calc(${getNodePosition(nodes.indexOf(sourceNode)).top} + 40px)`}
                x2={`calc(${getNodePosition(nodes.indexOf(targetNode)).left} + 40px)`}
                y2={`calc(${getNodePosition(nodes.indexOf(targetNode)).top} + 40px)`}
                stroke="#64748b"
                strokeWidth="2"
                markerEnd="url(#arrowhead)"
                opacity="0.5"
              />
            );
          })}
        </svg>

        {/* Nodes */}
        <div className="relative w-full h-full">
          {filteredNodes.map((node, index) => (
            <div
              key={node.id}
              className="absolute"
              style={getNodePosition(index)}
            >
              <button
                onClick={() => setSelectedNode(node)}
                className={`w-20 h-20 rounded-lg border-2 flex flex-col items-center justify-center cursor-pointer transition-all hover:scale-110 ${getNodeColor(
                  node.classification
                )} ${
                  selectedNode?.id === node.id
                    ? "ring-2 ring-cyan-400 scale-110"
                    : ""
                }`}
              >
                <div className="text-2xl">{getTypeIcon(node.type)}</div>
                <div className="text-xs text-slate-200 font-semibold mt-1">
                  {node.action_count}
                </div>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Details Panel */}
      {selectedNode && (
        <div className="mt-4 bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white">{selectedNode.label}</h3>
              <span
                className={`text-xs font-semibold uppercase ${
                  selectedNode.classification === "green"
                    ? "text-green-400"
                    : selectedNode.classification === "yellow"
                      ? "text-yellow-400"
                      : "text-red-400"
                }`}
              >
                {selectedNode.classification}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-slate-400">Type</div>
                <div className="text-slate-200">{selectedNode.type}</div>
              </div>
              <div>
                <div className="text-slate-400">Actions</div>
                <div className="text-slate-200">{selectedNode.action_count}</div>
              </div>
              <div>
                <div className="text-slate-400">ID</div>
                <div className="text-xs text-slate-300 font-mono truncate">
                  {selectedNode.id.substring(0, 12)}...
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-slate-400">Safe</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-yellow-500" />
          <span className="text-slate-400">Risky</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-slate-400">Dangerous</span>
        </div>
      </div>
    </div>
  );
}
