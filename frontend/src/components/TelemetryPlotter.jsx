import React, { useState, useEffect, useRef } from 'react';

export default function TelemetryPlotter({ telemetry }) {
  const { speedKmh, lidarDistM, riskScore } = telemetry;
  const [history, setHistory] = useState([]);
  const canvasRef = useRef(null);

  // Accumulate historical telemetry data points
  useEffect(() => {
    setHistory((prev) => {
      const next = [
        ...prev,
        {
          speed: speedKmh,
          lidar: lidarDistM,
          risk: riskScore,
        },
      ];
      if (next.length > 100) next.shift();
      return next;
    });
  }, [speedKmh, lidarDistM, riskScore]);

  // Render dark theme canvas line chart in responsive container
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Draw background (matching #101F33 Cardbg)
    ctx.fillStyle = '#101F33';
    ctx.fillRect(0, 0, width, height);

    // Draw subtle grid lines (matching #263B55 Slate Blue, very faint)
    ctx.strokeStyle = 'rgba(38, 59, 85, 0.4)';
    ctx.lineWidth = 1;
    for (let y = 15; y < height; y += 25) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    for (let x = 0; x < width; x += 50) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    if (history.length < 2) return;

    // Draw Line helper
    const drawLine = (key, color, maxVal) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      
      const xStep = width / 99; // for 100 points max
      
      history.forEach((pt, idx) => {
        const x = idx * xStep;
        const y = height - ((pt[key] / maxVal) * (height - 20)) - 10;
        
        if (idx === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
    };

    // Draw curves matching target specifications
    drawLine('speed', '#00A8FF', 120); // Speed (Electric Blue)
    drawLine('lidar', '#FF9F1C', 30);  // LiDAR (Orange)
    drawLine('risk', '#FF3B4D', 100);  // Risk (Red)
  }, [history]);

  return (
    <div className="glass-panel p-3.5 rounded-2xl border border-borderblue shadow-lg bg-cardbg h-full min-h-0 flex flex-col gap-2">
      <div className="flex items-center justify-between text-[11px] font-bold text-textgrey font-mono">
        <span>ADAS REAL-TIME FUSION PLOTTER</span>
        <div className="flex gap-3 text-[9px]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-[#00A8FF] inline-block"></span>Speed</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-[#FF9F1C] inline-block"></span>LiDAR</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-[#FF3B4D] inline-block"></span>Risk</span>
        </div>
      </div>
      <div className="relative flex-grow rounded-xl overflow-hidden bg-slate-950 border border-borderblue min-h-0">
        <canvas ref={canvasRef} width={800} height={120} className="w-full h-full block" />
      </div>
    </div>
  );
}
