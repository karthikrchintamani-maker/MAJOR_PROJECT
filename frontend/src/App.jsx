import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import TelemetryGauges from './components/TelemetryGauges';
import TelemetryPlotter from './components/TelemetryPlotter';
import WarningsBanner from './components/WarningsBanner';
import CameraStream from './components/CameraStream';
import GpsMap from './components/GpsMap';
import SensorHealth from './components/SensorHealth';
import VideoSourcePanel from './components/VideoSourcePanel';
import {
  Terminal,
  Settings,
  Sliders,
  Volume2,
  ShieldAlert,
  ShieldCheck,
  Cpu,
  Radio,
  AlertOctagon,
  Eye,
  Crosshair,
  Wifi,
  WifiOff,
  Download,
  Trash2,
} from 'lucide-react';

const BACKEND_BASE = 'http://localhost:5001';
const WS_URL       = 'ws://localhost:5001/ws/telemetry';

// ── Warning type → display structure ────────────────────────────────────────
function parseWarning(warnings) {
  if (!warnings || warnings.length === 0) return null;
  const w = warnings[0];
  if (w.startsWith('PEDESTRIAN_AHEAD')) {
    return { type: 'PEDESTRIAN_AHEAD', severity: 2, message: 'PEDESTRIAN DETECTED — REDUCE SPEED', timeToCollision: 4.5, distanceToTarget: 8 };
  }
  if (w.startsWith('POTHOLE_AHEAD')) {
    return { type: 'POTHOLE_AHEAD', severity: 3, message: 'ROAD ANOMALY DETECTED — BRAKE RECOMMENDED', timeToCollision: 2.5, distanceToTarget: 6 };
  }
  if (w.startsWith('HIGH_RISK')) {
    const score = w.split(':')[1] || '75';
    return { type: 'HIGH_RISK', severity: 3, message: `HIGH RISK SCORE (${score}%) — CAUTION`, timeToCollision: 3, distanceToTarget: 5 };
  }
  return null;
}

export default function App() {
  const [activeScenario, setActiveScenario] = useState('city');
  const [activeTab, setActiveTab] = useState('Overview');

  // ── Backend connection state ────────────────────────────────────────────
  const [backendOnline, setBackendOnline] = useState(false);
  const [streamActive, setStreamActive] = useState(false);
  const [backendModels, setBackendModels] = useState({});
  const [backendMode, setBackendMode] = useState('simulation'); // 'simulation'|'onnx'|'torch'
  const wsRef = useRef(null);
  const wsReconnectTimer = useRef(null);

  // ── Telemetry (merged: simulation base + real backend overlay) ──────────
  const [telemetry, setTelemetry] = useState({
    speedKmh: 34.2,
    rpm: 1750,
    lidarDistM: 6.4,
    riskScore: 28.5,
    lat: 28.6139,
    lng: 77.2090,
    coolantTemp: 82,
    batteryVolt: 13.8,
    fps: 0,
    detections: 0,
    potholes: 0,
  });

  const [activeWarning, setActiveWarning] = useState(null);

  const [sensorHealth, setSensorHealth] = useState({
    camera: true, lidar: true, gps: true, imu: true,
    obd: true, gsm: true, fps: 24.8, systemLoad: 32.1, temp: 42.5,
  });

  const [toggles, setToggles] = useState({
    showBoxes: true, showDrivable: true, showLanes: true, showDepth: false,
  });

  const [settings, setSettings] = useState({
    sensitivity: 'Medium', audioAlerts: true, riskThreshold: 36,
  });

  const [logs, setLogs] = useState([
    `[${new Date().toLocaleTimeString()}] [System] RoadEye Level-3 ADAS Stack Online.`,
    `[${new Date().toLocaleTimeString()}] [Perception] Loaded C++ ONNX Models.`,
    `[${new Date().toLocaleTimeString()}] [Fusion] EKF fusion filter initialized.`,
  ]);

  const pushLog = useCallback((msg) => {
    const formatted = msg.startsWith('[') ? msg : `[${new Date().toLocaleTimeString()}] ${msg}`;
    setLogs(prev => [formatted, ...prev.slice(0, 299)]);
  }, []);

  const downloadLogs = useCallback(() => {
    const content = logs.join('\n');
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `roadeye_operations_${new Date().toISOString().replace(/[:.]/g, '-')}.log`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [logs]);

  // Fetch recorded logs from backend when online
  useEffect(() => {
    if (!backendOnline) return;
    fetch(`${BACKEND_BASE}/api/logs?limit=50`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data.logs) && data.logs.length > 0) {
          setLogs(prev => {
            const reversed = [...data.logs].reverse();
            const combined = [...reversed, ...prev.filter(l => !data.logs.includes(l))];
            return combined.slice(0, 300);
          });
        }
      })
      .catch(() => {});
  }, [backendOnline]);

  // ══════════════════════════════════════════════════════════════════════════
  //  BACKEND POLLING — health check every 3s
  // ══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${BACKEND_BASE}/api/status`, { signal: AbortSignal.timeout(2000) });
        if (res.ok) {
          const data = await res.json();
          if (!backendOnline) {
            setBackendOnline(true);
            pushLog('[Backend] Connected to RoadEye inference server.');
            setBackendModels(data.models || {});
          }
          setStreamActive(data.running);
        } else {
          throw new Error('non-200');
        }
      } catch {
        if (backendOnline) {
          setBackendOnline(false);
          setStreamActive(false);
          pushLog('[Backend] Connection lost — falling back to simulation.');
        }
      }
    };

    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, [backendOnline, pushLog]);

  // ══════════════════════════════════════════════════════════════════════════
  //  WEBSOCKET — real-time telemetry from backend
  // ══════════════════════════════════════════════════════════════════════════
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        pushLog('[WebSocket] Real-time telemetry stream connected.');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setTelemetry(prev => ({
            ...prev,
            riskScore:    data.riskScore ?? prev.riskScore,
            lidarDistM:   data.closestDistM || prev.lidarDistM,
            fps:          data.fps || prev.fps,
            detections:   data.detections ?? prev.detections,
            potholes:     data.potholes ?? prev.potholes,
          }));

          // Track actual inference mode from backend
          if (data.mode) setBackendMode(data.mode);

          // Ingest real-time operations logs from backend
          if (Array.isArray(data.logs) && data.logs.length > 0) {
            setLogs(prev => {
              const newItems = data.logs.filter(l => !prev.includes(l));
              if (newItems.length === 0) return prev;
              return [...newItems.reverse(), ...prev].slice(0, 300);
            });
          }

          if (data.warnings?.length > 0) {
            setActiveWarning(parseWarning(data.warnings));
          } else {
            setActiveWarning(null);
          }

          setSensorHealth(prev => ({
            ...prev,
            fps:        data.fps || prev.fps,
            camera:     data.source !== 'none',
          }));
        } catch (e) { /* ignore parse errors */ }
      };

      ws.onerror = () => {};
      ws.onclose = () => {
        // Auto-reconnect after 3s if backend is up
        wsReconnectTimer.current = setTimeout(connectWS, 3000);
      };
    } catch { /* WebSocket may not be available yet */ }
  }, [pushLog]);

  useEffect(() => {
    if (backendOnline) connectWS();
    return () => {
      clearTimeout(wsReconnectTimer.current);
      wsRef.current?.close();
    };
  }, [backendOnline, connectWS]);

  // ══════════════════════════════════════════════════════════════════════════
  //  SIMULATION LOOP (only when backend is offline)
  // ══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    let speed = 32.5, rpm = 1680, lidar = 7.2, risk = 24.0, warn = null;
    let health = { camera: true, lidar: true, gps: true, imu: true, obd: true, gsm: true, fps: 24.8, systemLoad: 32.1, temp: 42.5 };

    if (activeScenario === 'city') {
      warn = { type: 'PEDESTRIAN_AHEAD', severity: 2, message: 'PEDESTRIAN ON ROAD EDGE — REDUCE SPEED', timeToCollision: 4.8, distanceToTarget: 8.5 };
    } else if (activeScenario === 'highway') {
      speed = 88.4; rpm = 2950; lidar = 24.5; risk = 12.0;
      health.systemLoad = 48.4; health.temp = 52.1;
    } else if (activeScenario === 'pothole') {
      speed = 42.1; rpm = 1920; lidar = 6.2; risk = 68.2;
      warn = { type: 'POTHOLE_AHEAD', severity: 3, message: 'POTHOLE SEVERITY HIGH (8.5CM) 6.2M AHEAD — BRAKE RECOMMENDATION', timeToCollision: 2.2, distanceToTarget: 6.2 };
    } else if (activeScenario === 'emergency') {
      speed = 0; rpm = 0; lidar = 0; risk = 100;
      warn = { type: 'CRASH_IMPACT', severity: 4, message: 'CRITICAL: COLLISION DETECTED (>4.2G IMPACT) — DISPATCHING SOS SMS via SIM800L', timeToCollision: 0.0, distanceToTarget: 0.0 };
      health.imu = false; health.obd = false;
    }

    if (!backendOnline) {
      setTelemetry(prev => ({ ...prev, speedKmh: speed, rpm, lidarDistM: lidar, riskScore: risk }));
      setActiveWarning(warn);
      setSensorHealth(prev => ({ ...prev, ...health }));
    }
  }, [activeScenario, backendOnline]);

  // Simulation oscillation loop (offline only)
  useEffect(() => {
    if (backendOnline) return;
    const id = setInterval(() => {
      if (activeScenario === 'emergency') return;
      setTelemetry(prev => {
        const t = Date.now() / 1000;
        return {
          ...prev,
          speedKmh:   +(prev.speedKmh  + Math.sin(t) * 0.3).toFixed(1),
          rpm:        Math.round(prev.rpm + Math.sin(t) * 15),
          lidarDistM: +(prev.lidarDistM + Math.sin(t * 1.5) * 0.12).toFixed(1),
          riskScore:  Math.min(100, Math.max(0, +(prev.riskScore + Math.sin(t * 0.8) * 0.8).toFixed(1))),
          lat: +(28.6139 + Math.sin(t / 60) * 0.0015).toFixed(5),
          lng: +(77.2090 + Math.cos(t / 60) * 0.0015).toFixed(5),
        };
      });
    }, 100);
    return () => clearInterval(id);
  }, [activeScenario, backendOnline]);

  // Simulated log loop (offline only)
  useEffect(() => {
    if (backendOnline) return;
    const msgs = {
      city:      ['Perception: Bounding boxes updated — 1 auto_rickshaw (94%), 1 pedestrian (88%).', 'Fusion: Spatially tracking pedestrian target (Offset: -1.8m).', 'Decision: Calculated TTC = 4.8s.', 'Sensor Bridge: Received ESP32 telemetry packet over 8888/UDP.'],
      highway:   ['Perception: Lane boundaries detected — solid left marker, dashed right marker.', 'Decision: Lane departure alert state: NOMINAL.', 'Fusion: Spatially tracking target vehicle ahead at 24.5m.'],
      pothole:   ['Perception: Pothole segment mask mapped to drivable region.', 'Decision: AUTOMATIC EMERGENCY BRAKE recommended (Decel rate: -3.8m/s²).', 'Fusion: EKF fused camera & LiDAR anomaly coordinates.'],
      emergency: ['Emergency: IMPACT DETECTED! G-Force peak = 4.25g.', 'Emergency: OBD-II speed drop verified.', 'Emergency: SOS Alert dispatched.'],
    };
    const id = setInterval(() => {
      const list = msgs[activeScenario] || [];
      if (list.length > 0) pushLog(list[Math.floor(Math.random() * list.length)]);
    }, 2500);
    return () => clearInterval(id);
  }, [activeScenario, backendOnline, pushLog]);

  // ── Source change handler ────────────────────────────────────────────────
  const handleSourceChanged = useCallback((source, active) => {
    setStreamActive(active);
    if (active) pushLog(`[Video] Pipeline started — source: ${source.toUpperCase()}`);
    else         pushLog('[Video] Pipeline stopped.');
  }, [pushLog]);

  // ════════════════════════════════════════════════════════════════════════
  //  RENDER
  // ════════════════════════════════════════════════════════════════════════
  return (
    <div className="h-screen max-h-screen bg-darkbg text-slate-100 flex p-3 gap-3 max-w-[1920px] mx-auto overflow-hidden">
      {/* 1. Sidebar */}
      <Sidebar activeScenario={activeScenario} setActiveScenario={setActiveScenario}
               activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* 2. Main Content */}
      <div className="flex-1 flex flex-col gap-3 h-full min-h-0 overflow-hidden">
        <Header activeScenario={activeScenario} />

        {/* ── TAB: Overview ─────────────────────────────────────────────── */}
        {activeTab === 'Overview' && (
          <>
            <WarningsBanner alert={activeWarning} />

            <div className="h-[450px] min-h-[450px] flex-shrink-0 grid grid-cols-12 gap-3">
              {/* Left panel — target dist + scenario selector */}
              <div className="col-span-2 glass-panel p-3 rounded-2xl border border-white/5 bg-cardbg flex flex-col justify-between shadow-lg">
                <div className="flex flex-col gap-0.5 border-b border-white/5 pb-2">
                  <span className="text-[9px] text-slate-400 font-bold font-mono uppercase">TARGET DIST@M</span>
                  <span className="text-xl font-extrabold text-blue-400 font-mono">
                    {activeScenario === 'emergency' ? '0.00 M' : `${(telemetry.lidarDistM || 0).toFixed(2)} M`}
                  </span>
                  {backendOnline && (
                    <span className="text-[9px] text-green-400 font-bold font-mono">
                      {telemetry.detections} obj | {telemetry.potholes} potholes
                    </span>
                  )}
                  <span className="text-[9px] text-[#22C55E] font-bold mt-0.5 font-mono uppercase">
                    AUDIO TRIGGER: ACTIVE
                  </span>
                </div>

                <div className="flex flex-col gap-2 flex-grow justify-end">
                  {/* Backend status badge */}
                  <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[9px] font-mono font-bold ${
                    backendOnline
                      ? 'text-green-400 border-green-400/30 bg-green-400/10'
                      : 'text-amber-400 border-amber-400/30 bg-amber-400/10'
                  }`}>
                    {backendOnline
                      ? <><Wifi className="w-3 h-3" /> BACKEND LIVE</>
                      : <><WifiOff className="w-3 h-3" /> SIMULATION</>}
                  </div>

                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-300 font-mono">
                    <Sliders className="w-3.5 h-3.5 text-blue-400" />
                    <span>SELECT TESTING SCENARIO</span>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {[['city','🏙️ Chaotic City Traffic'],['highway','🛣️ Highway Cruise'],['pothole','⚠️ Pothole Ahead'],['emergency','🚨 Crash SOS Trigger']].map(([id, label]) => (
                      <button key={id} onClick={() => setActiveScenario(id)}
                        className={`w-full py-1.5 px-3 rounded-lg text-[10px] font-bold font-mono text-left border flex items-center gap-2 transition-all ${
                          activeScenario === id
                            ? id === 'emergency'
                              ? 'bg-criticalred border-criticalred text-white shadow-sm animate-pulse'
                              : 'active-nav-gradient border-primaryaccent'
                            : 'bg-white/5 border-white/10 text-slate-300 hover:border-borderblue hover:bg-cardhover'
                        }`}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Camera stream (8 cols) */}
              <div className="col-span-8 h-full min-h-0">
                <CameraStream toggles={toggles} activeScenario={activeScenario}
                              backendOnline={backendOnline} streamActive={streamActive}
                              backendMode={backendMode} />
              </div>

              {/* Right panel — system status + ADAS config */}
              <div className="col-span-2 glass-panel p-3 rounded-2xl border border-white/5 bg-cardbg flex flex-col justify-between shadow-lg">
                <div className="flex flex-col gap-0.5 border-b border-white/5 pb-2">
                  <span className="text-[9px] text-textgrey font-bold font-mono uppercase">SYSTEM STATUS</span>
                  <span className={`text-md font-extrabold uppercase font-mono ${activeScenario === 'emergency' ? 'text-[#FF3B4D]' : 'text-[#22C55E]'}`}>
                    {activeScenario === 'emergency' ? 'SYS CRITICAL' : 'SYS ONLINE'}
                  </span>
                  <div className="grid grid-cols-2 gap-2 mt-1 text-[9px] font-mono text-textgrey">
                    <div><span className="block text-slate-500">Severity</span>
                      <span className={`font-bold text-[10px] ${activeScenario === 'emergency' ? 'text-criticalred' : 'text-slate-300'}`}>
                        {activeScenario === 'emergency' ? 'L4 | TC' : 'L0 | NOMINAL'}
                      </span>
                    </div>
                    <div><span className="block text-slate-500">Risk Level</span>
                      <span className={`font-bold text-[10px] ${activeScenario === 'emergency' ? 'text-criticalred' : 'text-slate-300'}`}>
                        {activeScenario === 'emergency' ? 'HIGH' : 'LOW'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-2 flex-grow justify-end">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-300 font-mono border-b border-white/5 pb-1">
                    <Settings className="w-3.5 h-3.5 text-primaryaccent" /><span>ADAS CONFIG</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[9px] text-slate-400 font-bold font-mono">FCW SENSITIVITY</span>
                    <div className="grid grid-cols-3 gap-1">
                      {['Low','Medium','High'].map(s => (
                        <button key={s} onClick={() => setSettings(prev => ({ ...prev, sensitivity: s }))}
                          className={`py-0.5 rounded text-[9px] font-mono font-bold border transition-all ${settings.sensitivity === s ? 'primary-btn-gradient border-primaryaccent text-white shadow-sm' : 'bg-white/5 border-white/10 text-slate-400 hover:border-white/20'}`}>
                          {s.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between text-[9px] text-slate-400 font-bold font-mono">
                      <span>WARNING THRESHOLD</span>
                      <span className="text-primaryaccent font-bold">{settings.riskThreshold}%</span>
                    </div>
                    <input type="range" min="20" max="80" value={settings.riskThreshold}
                      onChange={e => setSettings(prev => ({ ...prev, riskThreshold: +e.target.value }))}
                      className="w-full accent-primaryaccent bg-[#07111F] h-1 rounded-full cursor-pointer" />
                  </div>
                  <div className="flex items-center justify-between bg-white/5 p-1.5 rounded-lg border border-white/10">
                    <div className="flex items-center gap-1 text-[9px] font-mono font-bold text-slate-300">
                      <Volume2 className={`w-3.5 h-3.5 ${settings.audioAlerts ? 'text-primaryaccent' : 'text-slate-500'}`} />
                      <span>ADAS SOUNDS</span>
                    </div>
                    <input type="checkbox" checked={settings.audioAlerts}
                      onChange={e => setSettings(prev => ({ ...prev, audioAlerts: e.target.checked }))}
                      className="w-3 h-3 accent-primaryaccent cursor-pointer" />
                  </div>
                </div>
              </div>
            </div>

            <TelemetryGauges telemetry={telemetry} />

            <div className="h-[135px] min-h-[135px] flex-shrink-0 grid grid-cols-12 gap-3">
              <div className="col-span-8 h-full min-h-0"><TelemetryPlotter telemetry={telemetry} /></div>
              <div className="col-span-4 h-full min-h-0"><SensorHealth health={sensorHealth} /></div>
            </div>

            <div className="flex-1 min-h-0 grid grid-cols-12 gap-3">
              <div className="col-span-6 h-full min-h-0"><GpsMap lat={telemetry.lat} lng={telemetry.lng} activeScenario={activeScenario} /></div>
              <div className="col-span-6 glass-panel p-3 rounded-2xl border border-borderblue bg-cardbg flex flex-col gap-1.5 shadow-lg h-full min-h-0">
                <div className="flex items-center justify-between border-b border-borderblue pb-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-100">
                    <Terminal className="w-4 h-4 text-primaryaccent" /><span>REAL-TIME EVENT STREAM</span>
                  </div>
                  <button onClick={() => setLogs([])} className="text-[9px] px-2 py-0.5 rounded border border-white/10 bg-white/5 text-slate-400 font-bold hover:bg-white/10 active:scale-95">Clear All</button>
                </div>
                <div className="flex-grow bg-slate-950 rounded-xl p-2.5 font-mono text-[9px] overflow-y-auto custom-scrollbar flex flex-col gap-1 border border-borderblue shadow-inner select-all min-h-0">
                  {logs.map((l, i) => {
                    const isErr = l.includes('CRITICAL') || l.includes('IMPACT') || l.includes('Emergency') || l.includes('CRASH') || l.includes('Safety Alert');
                    const isPerception = l.includes('[Perception]');
                    const isTelemetry = l.includes('[Telemetry]');
                    return (
                      <div
                        key={i}
                        className={
                          isErr ? 'text-criticalred font-bold'
                          : isPerception ? 'text-emerald-400 font-medium'
                          : isTelemetry ? 'text-cyan-300'
                          : l.includes('[Scenario]') || l.includes('[Video]') || l.includes('[Backend]') || l.includes('[Upload]') ? 'text-[#F59E0B]'
                          : 'text-[#00E5FF]/90'
                        }
                      >
                        {l}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── TAB: Video Input ──────────────────────────────────────────── */}
        {activeTab === 'Video Input' && (
          <div className="flex-1 min-h-0 grid grid-cols-12 gap-3">
            <div className="col-span-4 h-full min-h-0">
              <VideoSourcePanel
                onSourceChanged={handleSourceChanged}
                backendOnline={backendOnline}
              />
            </div>
            <div className="col-span-8 h-full min-h-0 flex flex-col gap-3">
              {/* Model status cards */}
              <div className="glass-panel p-4 border border-borderblue bg-cardbg rounded-2xl">
                <div className="flex items-center gap-2 border-b border-borderblue pb-2 mb-3">
                  <Cpu className="w-4 h-4 text-primaryaccent" />
                  <span className="text-xs font-bold text-textlight font-mono">PERCEPTION MODEL STATUS</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries({
                    'Object Detection':  { key: 'detection',    desc: 'YOLO26n Indian Roads (48 classes)' },
                    'Road Segmentation': { key: 'segmentation', desc: 'YOLO11m Road Seg (drivable area)' },
                    'Pothole Detection': { key: 'pothole',      desc: 'YOLOv8s (5 crack/pothole types)' },
                    'Depth Estimation':  { key: 'depth',        desc: 'UNet Depthwise Nano (dense depth)' },
                  }).map(([label, { key, desc }]) => {
                    const m = backendModels[key];
                    const isReal = m && m.backend !== 'simulation' && !m.stub;
                    const isStub = m && m.stub;
                    return (
                      <div key={key} className={`p-3 rounded-xl border ${isReal ? 'border-green-400/30 bg-green-400/5' : 'border-amber-400/30 bg-amber-400/5'}`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] font-bold font-mono text-slate-200">{label}</span>
                          <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${isReal ? 'text-green-400 bg-green-400/20' : 'text-amber-400 bg-amber-400/20'}`}>
                            {!m ? 'NOT CONNECTED' : isStub ? 'LFS STUB' : m.backend.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-[9px] text-slate-500 font-mono">{desc}</p>
                        {isStub && (
                          <p className="text-[9px] text-amber-400 font-mono mt-1">⚠ Run `git lfs pull` to download real weights</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Instructions */}
              {!backendOnline && (
                <div className="glass-panel p-4 border border-amber-400/30 bg-amber-400/5 rounded-2xl flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-amber-400">
                    <AlertOctagon className="w-4 h-4" />
                    <span className="text-xs font-bold font-mono">BACKEND NOT RUNNING</span>
                  </div>
                  <p className="text-[10px] font-mono text-slate-400">
                    Start the Python backend to enable real video inference:
                  </p>
                  <div className="bg-slate-950 rounded-lg p-3 font-mono text-[10px] text-green-400 border border-borderblue">
                    <div className="text-slate-500 mb-1"># In project root:</div>
                    <div>cd backend</div>
                    <div>python server.py</div>
                  </div>
                  <p className="text-[10px] text-slate-500 font-mono">
                    Or double-click <span className="text-primaryaccent">start_backend.bat</span> in the project root.
                  </p>
                </div>
              )}

              {backendOnline && (
                <div className="glass-panel p-4 border border-green-400/30 bg-green-400/5 rounded-2xl flex flex-col gap-1">
                  <div className="flex items-center gap-2 text-green-400">
                    <Wifi className="w-4 h-4" />
                    <span className="text-xs font-bold font-mono">BACKEND CONNECTED</span>
                  </div>
                  <p className="text-[10px] font-mono text-slate-400">
                    {streamActive ? '🔴 Pipeline running — video is being processed.' : 'Select a video source and click "Start Pipeline" to begin inference.'}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB: Live Stream ──────────────────────────────────────────── */}
        {activeTab === 'Live Stream' && (
          <div className="flex-grow min-h-0 flex flex-col gap-3">
            <div className="flex-grow min-h-0">
              <CameraStream toggles={toggles} activeScenario={activeScenario}
                            backendOnline={backendOnline} streamActive={streamActive}
                            backendMode={backendMode} />
            </div>
            <div className="glass-panel p-3.5 border border-borderblue bg-cardbg flex items-center justify-between shadow-lg">
              <div className="flex items-center gap-2 text-xs font-bold text-textlight font-mono">
                <ShieldAlert className="w-4 h-4 text-[#00A8FF]" /><span>CAMERA OVERLAY LAYERS:</span>
              </div>
              <div className="flex gap-6 text-[11px] font-mono text-textgrey">
                {[['showBoxes','YOLO Boxes'],['showLanes','Lane Boundaries'],['showDrivable','Drivable Mask'],['showDepth','Depth Heatmap']].map(([k, label]) => (
                  <label key={k} className="flex items-center gap-2 cursor-pointer select-none">
                    <input type="checkbox" checked={toggles[k]}
                      onChange={e => setToggles(p => ({ ...p, [k]: e.target.checked }))}
                      className="w-4 h-4 accent-primaryaccent" />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── TAB: Scenario Testing ─────────────────────────────────────── */}
        {activeTab === 'Scenario Testing' && (
          <div className="flex-1 min-h-0 grid grid-cols-12 gap-3">
            <div className="col-span-4 glass-panel p-5 border border-borderblue bg-cardbg flex flex-col justify-between shadow-lg h-full">
              <div className="flex flex-col gap-1 border-b border-borderblue pb-3">
                <span className="text-[10px] text-textgrey font-bold font-mono uppercase">TARGET RANGE DETECTED</span>
                <span className="text-2xl font-extrabold text-[#00A8FF] font-mono">
                  {activeScenario === 'emergency' ? '0.00 M' : `${(telemetry.lidarDistM || 0).toFixed(2)} M`}
                </span>
                <span className="text-[10px] text-successgreen font-bold mt-1 font-mono uppercase">AUDIO STATUS: ACTIVE (FCW MODULE)</span>
              </div>
              <div className="flex flex-col gap-3 flex-grow justify-center">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-100 font-mono">
                  <Sliders className="w-4.5 h-4.5 text-[#00A8FF]" /><span>SELECT ACTIVE TESTING SCENARIO</span>
                </div>
                <div className="flex flex-col gap-2">
                  {[['city','🏙️ Chaotic City Traffic'],['highway','🛣️ Highway Cruise'],['pothole','⚠️ Pothole Ahead'],['emergency','🚨 Crash SOS Trigger']].map(([id, label]) => (
                    <button key={id} onClick={() => setActiveScenario(id)}
                      className={`py-3 px-4 rounded-xl text-xs font-bold font-mono border text-left transition-all ${
                        activeScenario === id
                          ? id === 'emergency' ? 'bg-criticalred text-white shadow-sm border-criticalred animate-pulse' : 'active-nav-gradient border-primaryaccent'
                          : 'bg-white/5 border-white/10 text-slate-300 hover:border-borderblue'
                      }`}>{label}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="col-span-8 glass-panel p-4 border border-borderblue bg-cardbg flex flex-col gap-2 shadow-lg h-full min-h-0">
              <div className="flex items-center justify-between border-b border-borderblue pb-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                  <Terminal className="w-4.5 h-4.5 text-primaryaccent" /><span>SCENARIO VERIFICATION LOG STREAM</span>
                </div>
                <button onClick={() => setLogs([])} className="text-[9px] px-2 py-0.5 rounded border border-white/10 bg-white/5 text-slate-400 font-bold hover:bg-white/10 active:scale-95">Clear All</button>
              </div>
              <div className="flex-grow bg-slate-950 rounded-xl p-3 font-mono text-[9px] overflow-y-auto custom-scrollbar flex flex-col gap-1.5 border border-borderblue shadow-inner select-all min-h-0">
                {logs.map((l, i) => {
                  const isErr = l.includes('CRITICAL') || l.includes('IMPACT') || l.includes('Emergency') || l.includes('CRASH') || l.includes('Safety Alert');
                  const isPerception = l.includes('[Perception]');
                  const isTelemetry = l.includes('[Telemetry]');
                  return (
                    <div
                      key={i}
                      className={
                        isErr ? 'text-[#FF3B4D] font-bold animate-pulse'
                        : isPerception ? 'text-emerald-400 font-medium'
                        : isTelemetry ? 'text-cyan-300'
                        : l.includes('[Scenario]') || l.includes('[Video]') || l.includes('[Backend]') || l.includes('[Upload]') ? 'text-warningamber'
                        : 'text-cyan-400/90'
                      }
                    >
                      {l}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── TAB: Sensor Hub / System Health ───────────────────────────── */}
        {['Sensor Hub', 'System Health'].includes(activeTab) && (
          <div className="flex-1 min-h-0 grid grid-cols-12 gap-3">
            <div className="col-span-4 h-full"><SensorHealth health={sensorHealth} /></div>
            <div className="col-span-8 h-full"><GpsMap lat={telemetry.lat} lng={telemetry.lng} activeScenario={activeScenario} /></div>
          </div>
        )}

        {/* ── TAB: ADAS Alerts ──────────────────────────────────────────── */}
        {activeTab === 'ADAS Alerts' && (
          <div className="flex-1 min-h-0 flex flex-col gap-3">
            <WarningsBanner alert={activeWarning} />
            <div className="flex-1 glass-panel p-6 border border-borderblue bg-cardbg rounded-2xl flex flex-col gap-4 justify-center items-center text-center">
              <ShieldAlert className="w-12 h-12 text-[#FF3B4D] animate-pulse" />
              <div>
                <h3 className="text-lg font-bold text-slate-200">ADAS Active Warning Alert System</h3>
                <p className="text-sm text-textgrey max-w-md mt-1">
                  Active alert diagnostics. Select scenarios in <strong>Scenario Testing</strong> or start a video pipeline in <strong>Video Input</strong> to trigger real warnings.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB: Vehicle Telemetry ────────────────────────────────────── */}
        {activeTab === 'Vehicle Telemetry' && (
          <div className="flex-1 min-h-0 flex flex-col gap-3">
            <TelemetryGauges telemetry={telemetry} />
            <div className="flex-1 min-h-0"><TelemetryPlotter telemetry={telemetry} /></div>
          </div>
        )}

        {/* ── TAB: Logs & Events ───────────────────────────────────────── */}
        {activeTab === 'Logs & Events' && (
          <div className="flex-grow min-h-0 glass-panel p-4 border border-borderblue bg-cardbg flex flex-col gap-2 shadow-lg h-full">
            <div className="flex items-center justify-between border-b border-borderblue pb-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <Terminal className="w-4.5 h-4.5 text-primaryaccent" /><span>CRITICAL OPERATIONS LOGGING STREAM</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 rounded-full">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  RECORDING LIVE ({logs.length})
                </span>
                <button
                  onClick={downloadLogs}
                  className="flex items-center gap-1 text-[10px] px-2.5 py-1 rounded-lg border border-primaryaccent/40 bg-primaryaccent/10 text-primaryaccent font-mono font-bold hover:bg-primaryaccent/20 active:scale-95 transition-all"
                  title="Export recorded logs to file"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export Logs
                </button>
                <button
                  onClick={() => setLogs([])}
                  className="flex items-center gap-1 text-[10px] px-2.5 py-1 rounded-lg border border-white/10 bg-white/5 text-slate-400 font-mono font-bold hover:bg-white/10 active:scale-95 transition-all"
                >
                  <Trash2 className="w-3 h-3" />
                  Clear All
                </button>
              </div>
            </div>
            <div className="flex-grow bg-slate-950 rounded-xl p-4 font-mono text-[10px] overflow-y-auto custom-scrollbar flex flex-col gap-2 border border-borderblue shadow-inner select-all min-h-0">
              {logs.length === 0 ? (
                <div className="text-slate-500 italic py-6 text-center">No operation logs recorded yet. Start a video stream or scenario to record events.</div>
              ) : (
                logs.map((l, i) => {
                  const isErr = l.includes('CRITICAL') || l.includes('IMPACT') || l.includes('Emergency') || l.includes('CRASH') || l.includes('Safety Alert');
                  const isWarning = l.includes('⚠️') || l.includes('Road Anomaly') || l.includes('[Scenario]') || l.includes('[Backend]') || l.includes('[Video]') || l.includes('[Upload]');
                  const isPerception = l.includes('[Perception]');
                  const isTelemetry = l.includes('[Telemetry]');
                  return (
                    <div
                      key={i}
                      className={
                        isErr
                          ? 'text-[#FF3B4D] font-bold text-xs bg-red-950/20 px-2.5 py-1 rounded border-l-2 border-red-500'
                          : isWarning
                          ? 'text-warningamber font-semibold bg-amber-950/10 px-2.5 py-1 rounded border-l-2 border-amber-500'
                          : isPerception
                          ? 'text-emerald-400 font-medium bg-emerald-950/10 px-2.5 py-1 rounded border-l-2 border-emerald-500'
                          : isTelemetry
                          ? 'text-cyan-300 font-medium px-2.5 py-1 rounded border-l-2 border-cyan-500'
                          : 'text-[#00E5FF]/90 px-2.5 py-1'
                      }
                    >
                      {l}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* ── TAB: Settings ─────────────────────────────────────────────── */}
        {activeTab === 'Settings' && (
          <div className="flex-grow min-h-0 grid grid-cols-12 gap-3">
            <div className="col-span-4 glass-panel p-5 border border-borderblue bg-cardbg flex flex-col justify-between shadow-lg h-full">
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-300 font-mono border-b border-white/5 pb-2">
                  <Settings className="w-4 h-4 text-primaryaccent" /><span>ADAS CONFIG MATRIX</span>
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] text-slate-400 font-bold font-mono">FCW SENSITIVITY</span>
                  <div className="grid grid-cols-3 gap-1.5">
                    {['Low','Medium','High'].map(s => (
                      <button key={s} onClick={() => setSettings(prev => ({ ...prev, sensitivity: s }))}
                        className={`py-1.5 rounded text-[10px] font-mono font-bold border transition-all ${settings.sensitivity === s ? 'primary-btn-gradient border-primaryaccent text-white shadow-sm' : 'bg-white/5 border-white/10 text-slate-400 hover:border-white/20'}`}>
                        {s.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-[10px] text-slate-400 font-bold font-mono">
                    <span>RISK WARNING THRESHOLD</span>
                    <span className="text-[#00A8FF] font-bold">{settings.riskThreshold}%</span>
                  </div>
                  <input type="range" min="20" max="80" value={settings.riskThreshold}
                    onChange={e => setSettings(prev => ({ ...prev, riskThreshold: +e.target.value }))}
                    className="w-full accent-[#00A8FF] bg-[#07111F] h-1.5 rounded-full cursor-pointer" />
                </div>
                <div className="flex items-center justify-between bg-white/5 p-2 rounded-xl border border-white/10">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold text-slate-300">
                    <Volume2 className={`w-3.5 h-3.5 ${settings.audioAlerts ? 'text-primaryaccent' : 'text-slate-500'}`} />
                    <span>ADAS SOUND ALERTS</span>
                  </div>
                  <input type="checkbox" checked={settings.audioAlerts}
                    onChange={e => setSettings(prev => ({ ...prev, audioAlerts: e.target.checked }))}
                    className="w-3.5 h-3.5 accent-[#00A8FF] cursor-pointer" />
                </div>
              </div>
            </div>
            <div className="col-span-8 glass-panel p-5 border border-borderblue bg-cardbg rounded-2xl flex flex-col justify-center items-center text-center">
              <Settings className="w-12 h-12 text-[#00A8FF]" />
              <h3 className="text-md font-bold mt-2 text-slate-200">System Preferences</h3>
              <p className="text-xs text-textgrey mt-1">Configured for RoadEye Level-3 ADAS stacks.</p>
              <div className={`mt-4 flex items-center gap-2 text-xs font-mono font-bold ${backendOnline ? 'text-green-400' : 'text-amber-400'}`}>
                {backendOnline ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
                {backendOnline ? 'Backend: Connected (http://localhost:5000)' : 'Backend: Offline — start backend/server.py'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
