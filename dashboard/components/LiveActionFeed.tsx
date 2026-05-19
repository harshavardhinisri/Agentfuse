"use client";

import { useState, useEffect } from "react";
import { CheckCircle, AlertCircle, XCircle, RefreshCw } from "lucide-react";

interface Action {
  action_id: string;
  agent_id: string;
  action_type: string;
  command: string;
  target_resource: string;
  classification: "green" | "yellow" | "red";
  confidence: number;
  decision: string;
  reason: string;
  timestamp: string;
  duration_ms: number;
}

interface LiveActionFeedProps {
  agentId: string;
}

export default function LiveActionFeed({ agentId }: LiveActionFeedProps) {
  const [actions, setActions] = useState<Action[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);

    // Fetch initial actions
    const fetchActions = async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/api/actions/recent?agent_id=${agentId}&limit=50`
        );
        const data = await response.json();
        setActions(data || []);
        setLoading(false);
      } catch (error) {
        console.error("Failed to fetch actions:", error);
        setLoading(false);
      }
    };

    fetchActions();

    // Connect WebSocket
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(
      `${protocol}//localhost:8000/ws/actions/stream?agent_id=${agentId}`
    );

    ws.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "action_batch") {
          setActions(data.actions || []);
        }
      } catch (error) {
        console.error("Failed to parse message:", error);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setIsConnected(false);
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [agentId]);

  const getClassificationIcon = (classification: string) => {
    switch (classification) {
      case "green":
        return <CheckCircle size={16} className="text-green-400" />;
      case "yellow":
        return <AlertCircle size={16} className="text-yellow-400" />;
      case "red":
        return <XCircle size={16} className="text-red-400" />;
      default:
        return null;
    }
  };

  const getClassificationColor = (classification: string) => {
    switch (classification) {
      case "green":
        return "text-green-400";
      case "yellow":
        return "text-yellow-400";
      case "red":
        return "text-red-400";
      default:
        return "text-slate-400";
    }
  };

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case "approved":
        return "bg-green-500/20 text-green-300 border-green-500/30";
      case "flagged":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
      case "blocked":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      default:
        return "bg-slate-600/20 text-slate-300 border-slate-600/30";
    }
  };

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Live Action Feed</h2>
          <p className="text-sm text-slate-400 mt-1">
            Real-time stream of all agent tool calls
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-2 bg-slate-700/50 rounded-lg">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-xs text-slate-300">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors">
            <RefreshCw size={20} className="text-slate-400" />
          </button>
        </div>
      </div>

      {/* Actions List */}
      <div className="flex-1 overflow-auto space-y-2">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-slate-400">Loading actions...</div>
          </div>
        ) : actions.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-slate-400">No actions yet</div>
          </div>
        ) : (
          actions.map((action) => (
            <div
              key={action.action_id}
              className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 hover:bg-slate-800/70 transition-colors group"
            >
              {/* Row 1: Classification + Command */}
              <div className="flex items-start gap-3 mb-2">
                <div className="mt-1">
                  {getClassificationIcon(action.classification)}
                </div>
                <div className="flex-1">
                  <div className="font-mono text-sm text-slate-200 break-all">
                    {action.command}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    Type: {action.action_type}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-semibold uppercase ${getClassificationColor(
                      action.classification
                    )}`}
                  >
                    {action.classification}
                  </span>
                  <span className="text-xs text-slate-500">
                    {(action.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Row 2: Target + Decision + Time */}
              <div className="flex items-center justify-between text-xs ml-6">
                <div className="text-slate-400">
                  Target: <span className="text-slate-300">{action.target_resource}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-1 rounded border ${getDecisionBadge(
                      action.decision
                    )}`}
                  >
                    {action.decision}
                  </span>
                  <span className="text-slate-500">
                    {action.duration_ms.toFixed(1)}ms
                  </span>
                </div>
              </div>

              {/* Reason (hidden by default, show on hover) */}
              <div className="text-xs text-slate-400 mt-2 ml-6 max-h-0 overflow-hidden group-hover:max-h-20 transition-all">
                <div className="text-slate-500">Reason:</div>
                <div className="text-slate-300">{action.reason}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
