import React, { useRef, useEffect, useState } from 'react';
import { Camera, Eye, Crosshair, Wifi, WifiOff } from 'lucide-react';

const BACKEND_BASE = 'http://localhost:5001';
const STREAM_URL   = `${BACKEND_BASE}/stream/video`;

export default function CameraStream({ toggles, activeScenario, backendOnline, streamActive, backendMode }) {
  const imgRef = useRef(null);
  const canvasRef = useRef(null);
  const [imgError, setImgError] = useState(false);
  const [images, setImages] = useState({
    base: null,
    depth: null,
    detection: null,
    pothole: null,
    segment: null
  });

  // Preload local model images for high-fidelity fallback simulation
  useEffect(() => {
    const loadImg = (src) => {
      return new Promise((resolve) => {
        const img = new Image();
        img.src = src;
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
      });
    };

    Promise.all([
      loadImg('/test_road.jpg'),
      loadImg('/model_depth.jpg'),
      loadImg('/model_detection.jpg'),
      loadImg('/model_pothole.jpg'),
      loadImg('/model_segment.jpg'),
    ]).then(([base, depth, detection, pothole, segment]) => {
      setImages({ base, depth, detection, pothole, segment });
    });
  }, []);

  // ── Send overlay toggles to backend whenever they change ─────────────────
  useEffect(() => {
    if (!backendOnline) return;
    fetch(`${BACKEND_BASE}/api/overlays`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        showBoxes:    toggles.showBoxes,
        showDrivable: toggles.showDrivable,
        showLanes:    toggles.showLanes,
        showDepth:    toggles.showDepth,
      }),
    }).catch(() => {});
  }, [toggles, backendOnline]);

  // ── Canvas simulation fallback (used when backend is offline) ─────────────
  useEffect(() => {
    if (backendOnline && streamActive && !imgError) return;  // using real stream

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;

    const render = () => {
      // 1. Draw base scene (original test_road.jpg)
      if (images.base) {
        ctx.drawImage(images.base, 0, 0, 640, 480);
      } else {
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, 640, 480);
        ctx.fillStyle = '#1e293b';
        ctx.beginPath();
        ctx.moveTo(0, 480); ctx.lineTo(280, 240);
        ctx.lineTo(360, 240); ctx.lineTo(640, 480);
        ctx.fill();
      }

      // 2. Draw Drivable segment overlay
      if (toggles.showDrivable && images.segment) {
        ctx.save();
        ctx.globalAlpha = 0.55; // Blend segment transparently on top
        ctx.drawImage(images.segment, 0, 0, 640, 480);
        ctx.restore();
      }

      // 3. Draw Depth overlay
      if (toggles.showDepth && images.depth) {
        ctx.save();
        ctx.globalAlpha = 0.65; // Blend depth heatmap transparently on top
        ctx.drawImage(images.depth, 0, 0, 640, 480);
        ctx.restore();
      }

      // 4. Draw YOLO boxes
      if (toggles.showBoxes) {
        if (activeScenario === 'pothole' && images.pothole) {
          ctx.save();
          ctx.globalAlpha = 0.85;
          ctx.drawImage(images.pothole, 0, 0, 640, 480);
          ctx.restore();
        } else if (images.detection) {
          ctx.save();
          ctx.globalAlpha = 0.85;
          ctx.drawImage(images.detection, 0, 0, 640, 480);
          ctx.restore();
        }
      }

      // 5. Draw Lane Assist assist lines synthetically on top
      if (toggles.showLanes) {
        ctx.strokeStyle = '#00E5FF'; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.moveTo(0, 480); ctx.lineTo(280, 240); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(640, 480); ctx.lineTo(360, 240); ctx.stroke();
      }

      // Offline watermark
      if (!backendOnline || !streamActive) {
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.fillRect(0, 0, 640, 30);
        ctx.fillStyle = '#F59E0B'; ctx.font = 'bold 12px monospace';
        ctx.fillText('⚠ HIGH-FIDELITY SIMULATION MODE — real model outputs shown', 10, 20);
      }

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [toggles, activeScenario, backendOnline, streamActive, imgError, images]);

  const showRealStream = backendOnline && streamActive && !imgError;

  return (
    <div className="glass-panel rounded-2xl p-3 border border-borderblue shadow-lg bg-cardbg flex flex-col gap-2 h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-borderblue pb-1.5">
        <div className="flex items-center gap-2 text-xs font-bold text-textlight">
          <Camera className="w-4 h-4 text-primaryaccent" />
          <span>FRONT CAMERA PERCEPTION STREAM (VISION PILOT ONNX)</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          {/* Backend status pill */}
          <span className={`flex items-center gap-1.5 font-bold px-2 py-0.5 rounded border ${
            backendOnline
              ? 'text-green-400 border-green-400/30 bg-green-400/10'
              : 'text-amber-400 border-amber-400/30 bg-amber-400/10'
          }`}>
            {backendOnline ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {backendOnline ? 'BACKEND LIVE' : 'SIMULATION'}
          </span>
          <span className="flex items-center gap-1.5 text-successgreen font-bold">
            <Eye className="w-3.5 h-3.5" /> 640×480 @ 25 FPS
          </span>
          {/* Accurate inference mode badge */}
          <span className={`px-2 py-0.5 rounded border font-bold ${
            !backendOnline
              ? 'bg-cardhover text-slate-400 border-borderblue'
              : backendMode === 'simulation'
              ? 'bg-amber-400/10 text-amber-400 border-amber-400/30'
              : 'bg-green-400/10 text-green-400 border-green-400/30'
          }`}>
            {!backendOnline
              ? 'CANVAS SIM'
              : backendMode === 'simulation'
              ? '⚡ CV SIMULATION'
              : `✅ ${(backendMode || 'onnx').toUpperCase()} INFERENCE`}
          </span>
        </div>

      </div>

      {/* Stream area */}
      <div className="relative flex-grow rounded-xl overflow-hidden bg-black border border-borderblue min-h-0 w-full h-full flex items-center justify-center">
        {/* Real MJPEG stream */}
        {backendOnline && streamActive && (
          <img
            ref={imgRef}
            src={`${STREAM_URL}?t=${Date.now()}`}
            alt="RoadEye Live Stream"
            className={`w-full h-full object-fill ${imgError ? 'hidden' : 'block'}`}
            onError={() => setImgError(true)}
            onLoad={() => setImgError(false)}
            style={{ display: imgError ? 'none' : 'block' }}
          />
        )}

        {/* Canvas simulation (when backend offline or stream error) */}
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className="w-full h-full object-fill"
          style={{ display: showRealStream ? 'none' : 'block' }}
        />

        {/* Status overlay badge */}
        <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono flex items-center gap-2">
          <Crosshair className="w-3.5 h-3.5 text-criticalred animate-spin" />
          <span>
            STATUS:{' '}
            <span className={`font-bold uppercase ${
              showRealStream ? 'text-green-400' :
              activeScenario === 'highway' ? 'text-primaryaccent' :
              activeScenario === 'emergency' ? 'text-criticalred' : 'text-criticalred'
            }`}>
              {showRealStream
                ? 'LIVE INFERENCE'
                : activeScenario === 'highway' ? 'Monitoring'
                : activeScenario === 'emergency' ? 'SYS CRITICAL'
                : 'Alerting'}
            </span>
          </span>
        </div>

        {/* Stream source badge */}
        {showRealStream && (
          <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-md px-2 py-1 rounded border border-green-400/30 text-[10px] font-mono text-green-400 font-bold">
            🔴 LIVE
          </div>
        )}
      </div>
    </div>
  );
}
