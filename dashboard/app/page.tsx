"use client";

import { useState, useEffect } from "react";
import {
  Activity,
  Map,
  Clock,
  Settings,
  Zap,
  AlertCircle,
} from "lucide-react";
import Header from "@/components/Header";
import Navigation from "@/components/Navigation";
import LiveActionFeed from "@/components/LiveActionFeed";
import BlastRadiusMap from "@/components/BlastRadiusMap";
import RollbackUI from "@/components/RollbackUI";
import Stats from "@/components/Stats";

type View = "feed" | "blast-radius" | "rollback";

export default function Dashboard() {
  const [currentView, setCurrentView] = useState<View>("feed");
  const [agentId, setAgentId] = useState("claude-dev");
  const [stats, setStats] = useState({
    totalActions: 0,
    greenCount: 0,
    yellowCount: 0,
    redCount: 0,
    blockedCount: 0,
  });

  // Fetch initial stats
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/stats");
        const data = await response.json();
        setStats({
          totalActions: data.total_actions_logged || 0,
          greenCount: data.green_count || 0,
          yellowCount: data.yellow_count || 0,
          redCount: data.red_count || 0,
          blockedCount: data.blocked_actions || 0,
        });
      } catch (error) {
        console.error("Failed to fetch stats:", error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <Header agentId={agentId} onAgentChange={setAgentId} />

      <div className="flex h-[calc(100vh-64px)]">
        {/* Sidebar Navigation */}
        <Navigation currentView={currentView} onViewChange={setCurrentView} />

        {/* Main Content */}
        <main className="flex-1 overflow-hidden">
          <div className="h-full flex flex-col">
            {/* Quick Stats Bar */}
            <Stats stats={stats} />

            {/* View Content */}
            <div className="flex-1 overflow-auto">
              {currentView === "feed" && (
                <LiveActionFeed agentId={agentId} />
              )}
              {currentView === "blast-radius" && (
                <BlastRadiusMap agentId={agentId} />
              )}
              {currentView === "rollback" && (
                <RollbackUI agentId={agentId} />
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
