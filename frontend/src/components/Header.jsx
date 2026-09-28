import React from 'react';
import { ShieldCheck, Cpu, Radio, AlertOctagon } from 'lucide-react';

export default function Header({ activeScenario }) {
  const isEmergency = activeScenario === 'emergency';

  return (
    <header className="glass-panel rounded-2xl p-4 flex flex-wrap items-center justify-between shadow-lg bg-cardbg border-borderblue">
      {/* Title / Description */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-primaryaccent to-indigo-600 flex items-center justify-center glow-cyan shadow-md shadow-primaryaccent/10">
          <ShieldCheck className="w-6 h-6 text-white font-bold" />
        </div>
        <div>
          <h1 className="text-lg font-extrabold tracking-wide text-textlight flex items-center gap-2">
            RoadEye ADAS 
          </h1>
          <p className="text-xs text-textgrey font-medium">Level-3 Autonomous Safety Architecture for Indian Roads</p>
        </div>
      </div>

      {/* Real-time status badges */}
      <div className="flex items-center gap-6 text-xs font-mono">
        <div className="flex flex-col items-end">
          <span className="text-[10px] text-textgrey block font-semibold leading-tight">LATENCY</span>
          <span className="text-successgreen font-bold text-xs">08s</span>
        </div>

        {/* SOS Alert Badge */}
        {isEmergency ? (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-criticalred text-white font-sans font-extrabold tracking-wider uppercase animate-pulse border border-criticalred shadow-md shadow-criticalred/20">
            <AlertOctagon className="w-3.5 h-3.5" />
            <span>SOS TRIGGERED</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cardhover text-textgrey font-sans font-bold tracking-wider uppercase border border-borderblue">
            <span>SOS STANDBY</span>
          </div>
        )}

        {/* ROS2 Link State */}
        <div className="flex items-center gap-2 bg-cardhover px-3 py-1.5 rounded-lg border border-borderblue">
          <Radio className="w-3.5 h-3.5 text-successgreen animate-pulse" />
          <span className="text-textlight">ROS2 Humble: <span className="text-successgreen font-bold">ONLINE</span></span>
        </div>

        {/* Compute Node Type */}
        <div className="flex items-center gap-2 bg-cardhover px-3 py-1.5 rounded-lg border border-borderblue">
          <Cpu className="w-3.5 h-3.5 text-primaryaccent" />
          <span className="text-textlight">Compute: <span className="text-primaryaccent font-bold">RPI 5 (8GB)</span></span>
        </div>
      </div>
    </header>
  );
}
