"use client";

import { Activity, Map, Clock, HelpCircle } from "lucide-react";

type View = "feed" | "blast-radius" | "rollback";

interface NavigationProps {
  currentView: View;
  onViewChange: (view: View) => void;
}

export default function Navigation({
  currentView,
  onViewChange,
}: NavigationProps) {
  const views = [
    {
      id: "feed" as View,
      name: "Live Feed",
      icon: Activity,
      description: "Real-time action stream",
    },
    {
      id: "blast-radius" as View,
      name: "Blast Radius",
      icon: Map,
      description: "Resource impact map",
    },
    {
      id: "rollback" as View,
      name: "Rollback",
      icon: Clock,
      description: "Action timeline",
    },
  ];

  return (
    <nav className="w-64 bg-slate-800/50 backdrop-blur-sm border-r border-slate-700 flex flex-col">
      {/* Navigation Items */}
      <div className="flex-1 px-3 py-6 space-y-2">
        {views.map((view) => {
          const Icon = view.icon;
          const isActive = currentView === view.id;

          return (
            <button
              key={view.id}
              onClick={() => onViewChange(view.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                isActive
                  ? "bg-gradient-to-r from-blue-500/30 to-cyan-500/30 border border-blue-500/50 text-cyan-300"
                  : "text-slate-300 hover:bg-slate-700/50"
              }`}
            >
              <Icon
                size={20}
                className={isActive ? "text-cyan-400" : "text-slate-400"}
              />
              <div className="text-left">
                <div className="font-semibold">{view.name}</div>
                <div
                  className={`text-xs ${
                    isActive ? "text-cyan-400/70" : "text-slate-500"
                  }`}
                >
                  {view.description}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="border-t border-slate-700 p-4 space-y-3">
        <div className="text-xs text-slate-400 space-y-1">
          <p>
            <span className="font-semibold text-slate-300">API:</span> ws://localhost:8000
          </p>
          <p>
            <span className="font-semibold text-slate-300">Status:</span>{" "}
            <span className="text-green-400">Connected</span>
          </p>
        </div>
        <button className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 transition-colors text-sm text-slate-300">
          <HelpCircle size={16} />
          Help
        </button>
      </div>
    </nav>
  );
}
