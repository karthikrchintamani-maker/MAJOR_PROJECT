import React from 'react';
import { AlertTriangle, AlertOctagon } from 'lucide-react';

export default function WarningsBanner({ alert }) {
  if (!alert) return null;

  const isCritical = alert.severity >= 3;

  return (
    <div 
      style={{
        background: isCritical
          ? 'linear-gradient(90deg, rgba(255, 59, 77, 0.18), rgba(255, 59, 77, 0.04))'
          : 'linear-gradient(90deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.03))',
        borderColor: isCritical ? '#FF3B4D' : '#F59E0B',
      }}
      className="rounded-2xl p-4 flex items-center justify-between shadow-lg transition-all duration-300 border"
    >
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-xl ${isCritical ? 'bg-criticalred text-white glow-red animate-pulse' : 'bg-warningamber text-slate-950 glow-amber'}`}>
          {isCritical ? <AlertOctagon className="w-6 h-6" /> : <AlertTriangle className="w-6 h-6" />}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span 
              style={{
                backgroundColor: isCritical ? 'rgba(255, 59, 77, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: isCritical ? '#FF3B4D' : '#F59E0B',
                borderColor: isCritical ? 'rgba(255, 59, 77, 0.3)' : 'rgba(245, 158, 11, 0.3)',
              }}
              className="text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold"
            >
              SEVERITY L{alert.severity}
            </span>
            <span className="text-xs text-textgrey font-mono">TTC: {alert.timeToCollision.toFixed(1)}s</span>
          </div>
          <h2 className="text-md font-extrabold tracking-wide text-textlight mt-1">{alert.message}</h2>
        </div>
      </div>

      <div className="hidden md:flex items-center gap-6 font-mono text-xs text-textgrey">
        <div>
          <span className="text-[10px] text-slate-500 block font-semibold leading-tight">TARGET DIST</span>
          <span className="text-textlight font-bold text-sm">{alert.distanceToTarget}m</span>
        </div>
        <div>
          <span className="text-[10px] text-slate-500 block font-semibold leading-tight">AUDIO MODULE</span>
          <span className="text-successgreen font-bold text-sm">ACTIVE</span>
        </div>
      </div>
    </div>
  );
}
