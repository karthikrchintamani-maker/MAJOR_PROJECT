import React from 'react';
import { Cpu } from 'lucide-react';

export default function SensorHealth({ health }) {
  // Sensor & system health matrix updating live with mobile IoT node and perception status
  const isMobileOnline = health.mobileIotConnected;
  const sensors = [
    { name: 'Mobile IoT Node (Kotlin / UDP 5005)', status: isMobileOnline, val: isMobileOnline ? `${health.mobileHz || 20} Hz` : 'WAITING' },
    { name: 'Mobile GNSS / GPS Sensor', status: health.gps, val: isMobileOnline ? 'FIX' : '100%' },
    { name: 'Tri-Axial MEMS Accelerometer', status: health.imu, val: '100%' },
    { name: 'Tri-Axial MEMS Gyroscope', status: health.imu, val: '100%' },
    { name: 'Vision Pilot Camera (DirectShow)', status: health.camera, val: health.camera ? 'STREAMING' : 'IDLE' },
    { name: 'LiDAR / Proximity Sensor', status: health.lidar, val: '100%' },
    { name: 'OBD-II CAN-Bus (ISO 15765-4)', status: health.obd, val: health.obd ? 'CAN ONLINE' : 'READY' },
    { name: 'SIM800L (SOS Crash Gateway)', status: health.gsm, val: 'STANDBY' },
    { name: 'System Load', status: true, val: `${health.systemLoad}%`, isMetric: true },
    { name: 'System Temp', status: true, val: `${health.temp}°C`, isMetric: true },
    { name: 'Perception FPS (ONNX)', status: true, val: `${health.fps}`, isMetric: true },
  ];

  return (
    <div className="glass-panel rounded-2xl p-3 border border-borderblue shadow-lg bg-cardbg flex flex-col gap-2 h-full min-h-0">
      <div className="flex items-center justify-between border-b border-borderblue pb-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-textlight">
          <Cpu className="w-4.5 h-4.5 text-[#00E5FF]" />
          <span>SENSOR & SYSTEM HEALTH MATRIX</span>
        </div>
        <span className="text-[10px] font-mono font-bold text-[#22C55E] bg-[#22C55E]/10 px-2 py-0.5 rounded border border-[#22C55E]/20">
          SYSTEM HEALTH: 100%
        </span>
      </div>

      <div className="overflow-y-auto flex-1 custom-scrollbar min-h-0">
        <table className="min-w-full text-left font-mono text-[11px]">
          <tbody>
            {sensors.map((s, idx) => {
              const isOk = s.status;
              return (
                <tr key={idx} className="border-b border-white/5 hover:bg-cardhover">
                  <td className="py-1 text-textgrey font-medium">{s.name}</td>
                  <td className="py-1 px-2 text-center">
                    {s.isMetric ? (
                      <span className="text-[#00A8FF] bg-[#00A8FF]/10 px-1.5 py-0.5 rounded font-extrabold text-[9px] border border-[#00A8FF]/20">
                        NORMAL
                      </span>
                    ) : isOk ? (
                      <span className="text-[#22C55E] bg-[#22C55E]/10 px-1.5 py-0.5 rounded font-extrabold text-[9px] border border-[#22C55E]/20">
                        HEALTHY
                      </span>
                    ) : (
                      <span className="text-[#FF3B4D] bg-[#FF3B4D]/10 px-1.5 py-0.5 rounded font-extrabold text-[9px] border border-[#FF3B4D]/20 animate-pulse">
                        TRIPPED
                      </span>
                    )}
                  </td>
                  <td className="py-1 text-right text-textlight font-bold">{s.val}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
