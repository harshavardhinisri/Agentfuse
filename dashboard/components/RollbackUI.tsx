"use client";

import { useState, useEffect } from "react";
import {
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  CheckCircle,
} from "lucide-react";

interface TimelineEvent {
  index: number;
  action_id: string;
  timestamp: string;
  action_type: string;
  command: string;
  target: string;
  classification: string;
  decision: string;
  can_rollback: boolean;
}

interface RollbackUIProps {
  agentId: string;
}

export default function RollbackUI({ agentId }: RollbackUIProps) {
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [isConnected, setIsConnected] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isRollingBack, setIsRollingBack] = useState(false);

  useEffect(() => {
    // Connect WebSocket for timeline updates
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(
      `${protocol}//localhost:8000/ws/agents/${agentId}/timeline`
    );

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "timeline_update") {
          setTimeline(data.timeline || []);
          if (selectedIndex === 0) {
            setSelectedIndex(data.timeline.length - 1);
          }
        }
      } catch (error) {
        console.error("Failed to parse timeline data:", error);
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

  const handleRollback = async () => {
    if (selectedIndex === 0) return;

    setIsRollingBack(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/rollback/execute`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            agent_id: agentId,
            checkpoint_action_id: timeline[selectedIndex - 1]?.action_id,
          }),
        }
      );

      if (response.ok) {
        setShowConfirm(false);
        setSelectedIndex(selectedIndex - 1);
        // Show success message
        alert("Rollback executed successfully!");
      }
    } catch (error) {
      console.error("Rollback failed:", error);
      alert("Rollback failed. Please try again.");
    } finally {
      setIsRollingBack(false);
    }
  };

  const selectedEvent = timeline[selectedIndex];
  const rollbackCount = selectedIndex > 0 ? timeline.length - selectedIndex : 0;

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

  const getClassificationBg = (classification: string) => {
    switch (classification) {
      case "green":
        return "bg-green-500/10 border-green-500/30";
      case "yellow":
        return "bg-yellow-500/10 border-yellow-500/30";
      case "red":
        return "bg-red-500/10 border-red-500/30";
      default:
        return "bg-slate-600/10 border-slate-600/30";
    }
  };

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Rollback Timeline</h2>
          <p className="text-sm text-slate-400 mt-1">
            Step through actions and revert to any checkpoint
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-700/50 rounded-lg">
          <div
            className={`w-2 h-2 rounded-full ${
              isConnected ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <span className="text-xs text-slate-300">
            {isConnected ? "Live" : "Offline"}
          </span>
        </div>
      </div>

      {/* Timeline Slider */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 mb-6">
        <div className="space-y-4">
          {/* Visual Slider */}
          <div className="flex items-center gap-4">
            <button
              onClick={() =>
                setSelectedIndex(Math.max(0, selectedIndex - 1))
              }
              disabled={selectedIndex === 0}
              className="p-2 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              <ChevronLeft size={20} />
            </button>

            <div className="flex-1">
              <div className="relative h-2 bg-slate-700 rounded-full overflow-hidden">
                {/* Progress bar */}
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all"
                  style={{
                    width: `${(selectedIndex / Math.max(1, timeline.length - 1)) * 100}%`,
                  }}
                />

                {/* Slider thumb */}
                <input
                  type="range"
                  min="0"
                  max={Math.max(1, timeline.length - 1)}
                  value={selectedIndex}
                  onChange={(e) => setSelectedIndex(parseInt(e.target.value))}
                  className="absolute inset-0 w-full opacity-0 cursor-pointer"
                />
              </div>

              {/* Timeline labels */}
              <div className="flex justify-between text-xs text-slate-400 mt-2">
                <span>Start (Safe)</span>
                <span>
                  {selectedIndex + 1} / {timeline.length}
                </span>
                <span>Now (Current)</span>
              </div>
            </div>

            <button
              onClick={() =>
                setSelectedIndex(Math.min(timeline.length - 1, selectedIndex + 1))
              }
              disabled={selectedIndex === timeline.length - 1}
              className="p-2 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              <ChevronRight size={20} />
            </button>
          </div>

          {/* Rollback Info */}
          {rollbackCount > 0 && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex items-start gap-3">
              <AlertCircle size={20} className="text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-red-300">Rollback Preview</div>
                <div className="text-sm text-red-200 mt-1">
                  Rolling back {rollbackCount} action{rollbackCount > 1 ? "s" : ""}.
                  Compensating transactions will undo changes from this point
                  forward.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Selected Event Details */}
      {selectedEvent && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 mb-6">
          <h3 className="font-semibold text-white mb-4">
            Action #{selectedEvent.index + 1}
          </h3>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <div className="text-xs text-slate-400 mb-1">Type</div>
              <div className="text-slate-200">{selectedEvent.action_type}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Classification</div>
              <div className={`text-sm font-semibold uppercase ${getClassificationColor(selectedEvent.classification)}`}>
                {selectedEvent.classification}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Decision</div>
              <div className="text-slate-200">{selectedEvent.decision}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Timestamp</div>
              <div className="text-xs font-mono text-slate-300">
                {new Date(selectedEvent.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>

          {/* Command */}
          <div className="mb-4">
            <div className="text-xs text-slate-400 mb-2">Command</div>
            <div className="bg-slate-900/50 border border-slate-700 rounded p-3 font-mono text-sm text-slate-300 break-all">
              {selectedEvent.command}
            </div>
          </div>

          {/* Target */}
          <div>
            <div className="text-xs text-slate-400 mb-2">Target Resource</div>
            <div className="bg-slate-900/50 border border-slate-700 rounded p-3 font-mono text-sm text-slate-300 break-all">
              {selectedEvent.target}
            </div>
          </div>
        </div>
      )}

      {/* Compensating Transactions Preview */}
      {rollbackCount > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 mb-6">
          <h3 className="font-semibold text-white mb-4">
            Compensating Transactions ({rollbackCount})
          </h3>

          <div className="space-y-2 max-h-40 overflow-y-auto">
            {timeline
              .slice(selectedIndex + 1)
              .reverse()
              .map((event, i) => (
                <div
                  key={event.action_id}
                  className="bg-slate-900/50 border border-slate-700 rounded p-3 text-sm"
                >
                  <div className="text-slate-300">
                    <span className="text-yellow-400">UNDO:</span> {event.action_type}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {event.target}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Rollback Button */}
      {rollbackCount > 0 && (
        <div className="mt-auto">
          {!showConfirm ? (
            <button
              onClick={() => setShowConfirm(true)}
              className="w-full bg-gradient-to-r from-red-500 to-orange-500 hover:from-red-600 hover:to-orange-600 text-white font-semibold py-3 rounded-lg transition-all flex items-center justify-center gap-2"
            >
              <RotateCcw size={20} />
              Rollback to Checkpoint ({rollbackCount})
            </button>
          ) : (
            <div className="space-y-3">
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                <div className="font-semibold text-red-300 mb-2">
                  Confirm Rollback?
                </div>
                <p className="text-sm text-red-200">
                  This will execute {rollbackCount} compensating transaction
                  {rollbackCount > 1 ? "s" : ""} to undo all changes from this
                  checkpoint forward. This action cannot be undone.
                </p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setShowConfirm(false)}
                  disabled={isRollingBack}
                  className="flex-1 px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRollback}
                  disabled={isRollingBack}
                  className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  <RotateCcw size={18} />
                  {isRollingBack ? "Rolling back..." : "Confirm Rollback"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
