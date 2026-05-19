"use client";

import { CheckCircle, AlertCircle, XCircle, Zap } from "lucide-react";

interface StatsProps {
  stats: {
    totalActions: number;
    greenCount: number;
    yellowCount: number;
    redCount: number;
    blockedCount: number;
  };
}

export default function Stats({ stats }: StatsProps) {
  const statItems = [
    {
      label: "Total Actions",
      value: stats.totalActions,
      icon: Zap,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "Approved",
      value: stats.greenCount,
      icon: CheckCircle,
      color: "text-green-400",
      bg: "bg-green-500/10",
    },
    {
      label: "Flagged",
      value: stats.yellowCount,
      icon: AlertCircle,
      color: "text-yellow-400",
      bg: "bg-yellow-500/10",
    },
    {
      label: "Blocked",
      value: stats.redCount + stats.blockedCount,
      icon: XCircle,
      color: "text-red-400",
      bg: "bg-red-500/10",
    },
  ];

  return (
    <div className="bg-slate-800/30 border-b border-slate-700 px-6 py-4">
      <div className="grid grid-cols-4 gap-4">
        {statItems.map((item, index) => {
          const Icon = item.icon;
          return (
            <div
              key={index}
              className={`${item.bg} border border-slate-700 rounded-lg p-4 flex items-center gap-3`}
            >
              <Icon size={24} className={item.color} />
              <div>
                <div className="text-xs text-slate-400">{item.label}</div>
                <div className="text-2xl font-bold text-white">
                  {item.value}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
