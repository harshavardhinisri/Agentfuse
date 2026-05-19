"use client";

import { Shield, Settings } from "lucide-react";

interface HeaderProps {
  agentId: string;
  onAgentChange: (agentId: string) => void;
}

export default function Header({ agentId, onAgentChange }: HeaderProps) {
  const agents = [
    { id: "claude-dev", name: "Claude Dev", icon: "🤖" },
    { id: "claude-prod", name: "Claude Prod", icon: "⚙️" },
    { id: "automation-bot", name: "Automation Bot", icon: "🦾" },
    { id: "test-agent", name: "Test Agent", icon: "🧪" },
  ];

  return (
    <header className="bg-slate-900/50 backdrop-blur-md border-b border-slate-700 px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg">
            <Shield size={24} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">AgentFuse</h1>
            <p className="text-xs text-slate-400">Real-time Agent Monitor</p>
          </div>
        </div>

        {/* Agent Selector */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Monitoring:</label>
            <select
              value={agentId}
              onChange={(e) => onAgentChange(e.target.value)}
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm font-medium text-slate-50 hover:bg-slate-600 transition-colors"
            >
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.icon} {agent.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Indicator */}
          <div className="flex items-center gap-2 px-3 py-2 bg-green-500/10 border border-green-500/30 rounded-lg">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-green-300 font-medium">LIVE</span>
          </div>

          {/* Settings */}
          <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors">
            <Settings size={20} className="text-slate-400" />
          </button>
        </div>
      </div>
    </header>
  );
}
