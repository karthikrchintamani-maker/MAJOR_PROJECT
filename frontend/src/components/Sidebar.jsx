import React from 'react';
import { 
  LayoutDashboard, 
  Video, 
  Sliders, 
  Cpu, 
  AlertTriangle, 
  Gauge, 
  Activity, 
  Terminal, 
  Settings, 
  AlertOctagon 
} from 'lucide-react';

export default function Sidebar({ activeScenario, setActiveScenario, activeTab, setActiveTab }) {
  const menuItems = [
    { name: 'Overview', icon: LayoutDashboard },
    { name: 'Video Input', icon: Video },
    { name: 'Live Stream', icon: Activity },
    { name: 'Scenario Testing', icon: Sliders },
    { name: 'Sensor Hub', icon: Cpu },
    { name: 'ADAS Alerts', icon: AlertTriangle },
    { name: 'Vehicle Telemetry', icon: Gauge },
    { name: 'System Health', icon: Activity },
    { name: 'Logs & Events', icon: Terminal },
    { name: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 glass-panel flex flex-col gap-6 p-4 shadow-lg bg-sidebarbg border-borderblue">
      {/* Sidebar Header Title */}
      <div className="flex items-center gap-2 pb-4 border-b border-borderblue">
        <div className="w-8 h-8 rounded-lg bg-primaryaccent flex items-center justify-center text-white font-bold glow-cyan">
          RE
        </div>
        <div>
          <h2 className="text-md font-bold tracking-wider text-textlight">RoadEye ADAS</h2>
          <p className="text-[10px] text-textgrey uppercase font-mono tracking-tight">SYSTEM PROTOTYPE</p>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="flex flex-col gap-1.5 flex-1">
        {menuItems.map((item, idx) => {
          const Icon = item.icon;
          const isActive = activeTab === item.name;
          return (
            <button
              key={idx}
              onClick={() => setActiveTab(item.name)}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold tracking-wide transition-all duration-200 ${
                isActive
                  ? 'active-nav-gradient'
                  : 'text-textgrey hover:bg-cardhover hover:text-textlight'
              }`}
            >
              <Icon className={`w-4.5 h-4.5 ${isActive ? 'text-white' : 'text-textgrey'}`} />
              <span>{item.name}</span>
            </button>
          );
        })}
      </nav>

      {/* Critical Alert Widget */}
      <div 
        style={{
          background: 'linear-gradient(90deg, rgba(255, 59, 77, 0.18), rgba(255, 59, 77, 0.04))',
          borderColor: '#FF3B4D',
          color: '#FF3B4D'
        }}
        className="border p-3.5 rounded-xl flex flex-col gap-2 mt-auto"
      >
        <div className="flex items-center gap-2">
          <AlertOctagon className="w-5 h-5 text-criticalred animate-bounce" />
          <span className="text-[10px] font-bold text-criticalred tracking-wider uppercase font-mono">CRITICAL ALERT</span>
        </div>
        <div>
          <h4 className="text-xs font-bold text-textlight">Collision Detected</h4>
          <p className="text-[10px] text-criticalred font-bold font-mono">&gt;4.2G Impact</p>
          <p className="text-[10px] text-textgrey mt-1 font-mono leading-tight">Dispatching SOS SMS via SIM800L</p>
        </div>
        <button
          onClick={() => setActiveScenario('emergency')}
          className="w-full py-2 mt-1 rounded-lg bg-criticalred hover:bg-red-700 text-white font-bold text-xs tracking-wider uppercase transition-all shadow-md active:scale-95 border border-criticalred/20"
        >
          Trigger SOS Test
        </button>
      </div>
    </aside>
  );
}
