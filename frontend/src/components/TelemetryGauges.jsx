import React from 'react';
import { Gauge, Activity, Navigation, Zap } from 'lucide-react';

export default function TelemetryGauges({ telemetry }) {
  const { speedKmh, rpm, lidarDistM, riskScore } = telemetry;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 flex-shrink-0">
      {/* Speed Gauge (Electric Blue) */}
      <div className="glass-panel p-3.5 rounded-2xl flex flex-col justify-between relative overflow-hidden group shadow-lg bg-cardbg border-borderblue">
        <div className="flex items-center justify-between text-textgrey text-[10px] font-bold tracking-wider font-mono">
          <span>VEHICLE SPEED</span>
          <Gauge className="w-4 h-4 text-[#00A8FF] animate-pulse" />
        </div>
        <div className="my-2 flex items-baseline">
          <span className="text-4xl font-extrabold font-mono text-textlight tracking-tight">{speedKmh}</span>
          <span className="text-[10px] font-bold font-mono text-[#00A8FF] ml-1">KM/H</span>
        </div>
        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
          <div 
            className="bg-[#00A8FF] h-full transition-all duration-300 shadow-sm"
            style={{ width: `${Math.min(100, (speedKmh / 140) * 100)}%` }}
          />
        </div>
      </div>

      {/* RPM Gauge (Green) */}
      <div className="glass-panel p-3.5 rounded-2xl flex flex-col justify-between relative overflow-hidden group shadow-lg bg-cardbg border-borderblue">
        <div className="flex items-center justify-between text-textgrey text-[10px] font-bold tracking-wider font-mono">
          <span>ENGINE RPM</span>
          <Activity className="w-4 h-4 text-[#22C55E]" />
        </div>
        <div className="my-2 flex items-baseline">
          <span className="text-4xl font-extrabold font-mono text-textlight tracking-tight">{rpm}</span>
          <span className="text-[10px] font-bold font-mono text-[#22C55E] ml-1">RPM</span>
        </div>
        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
          <div 
            className="bg-[#22C55E] h-full transition-all duration-300 shadow-sm"
            style={{ width: `${Math.min(100, (rpm / 6000) * 100)}%` }}
          />
        </div>
      </div>

      {/* LiDAR Distance (Orange) */}
      <div className="glass-panel p-3.5 rounded-2xl flex flex-col justify-between relative overflow-hidden group shadow-lg bg-cardbg border-borderblue">
        <div className="flex items-center justify-between text-textgrey text-[10px] font-bold tracking-wider font-mono">
          <span>LiDAR TARGET DIST</span>
          <Navigation className="w-4 h-4 text-[#FF9F1C]" />
        </div>
        <div className="my-2 flex items-baseline">
          <span className="text-4xl font-extrabold font-mono text-textlight tracking-tight">{lidarDistM}</span>
          <span className="text-[10px] font-bold font-mono text-[#FF9F1C] ml-1">METERS</span>
        </div>
        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
          <div 
            className="bg-[#FF9F1C] h-full transition-all duration-300 shadow-sm"
            style={{ width: `${Math.min(100, (lidarDistM / 20) * 100)}%` }}
          />
        </div>
      </div>

      {/* Spatial Risk Score (Magenta/Red) */}
      <div className="glass-panel p-3.5 rounded-2xl flex flex-col justify-between relative overflow-hidden group shadow-lg bg-cardbg border-borderblue">
        <div className="flex items-center justify-between text-textgrey text-[10px] font-bold tracking-wider font-mono">
          <span>FUSED RISK SCORE</span>
          <Zap className="w-4 h-4 text-[#FF3D81]" />
        </div>
        <div className="my-2 flex items-baseline">
          <span className="text-4xl font-extrabold font-mono tracking-tight text-[#FF3D81]">
            {riskScore}
          </span>
          <span className="text-[10px] font-bold font-mono text-slate-500 ml-1">/100</span>
        </div>
        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
          <div 
            className="h-full transition-all duration-300 bg-[#FF3D81] shadow-md shadow-red-500/30"
            style={{ width: `${riskScore}%` }}
          />
        </div>
      </div>
    </div>
  );
}
