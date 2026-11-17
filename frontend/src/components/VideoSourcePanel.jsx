import React, { useState, useRef, useEffect } from 'react';
import {
  Video, Webcam, Radio, Upload, Play, Square,
  Link, CheckCircle, XCircle, Loader, AlertTriangle, RefreshCw
} from 'lucide-react';

const BACKEND_BASE = 'http://localhost:5001';

export default function VideoSourcePanel({ onSourceChanged, backendOnline, isRunning }) {
  const [source, setSource] = useState('webcam');   // 'webcam'|'espcam'|'upload'
  const [espcamUrl, setEspcamUrl] = useState('http://192.168.4.2/stream');
  const [running, setRunning] = useState(Boolean(isRunning));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [cameras, setCameras] = useState([]);
  const [selectedCam, setSelectedCam] = useState(1);
  const [loadingCams, setLoadingCams] = useState(false);
  const fileRef = useRef(null);

  // Sync running state from parent prop
  useEffect(() => {
    if (isRunning !== undefined) {
      setRunning(isRunning);
    }
  }, [isRunning]);

  // Sync state with backend on mount
  useEffect(() => {
    if (!backendOnline) return;
    fetch(`${BACKEND_BASE}/api/status`)
      .then(res => res.json())
      .then(data => {
        if (data.running !== undefined) setRunning(data.running);
        if (data.source && data.source !== 'none') setSource(data.source);
        if (data.webcam_index !== undefined) setSelectedCam(data.webcam_index);
      })
      .catch(() => {});
  }, [backendOnline]);

  const fetchCameras = async () => {
    if (!backendOnline) return;
    setLoadingCams(true);
    try {
      const resp = await fetch(`${BACKEND_BASE}/api/cameras`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.cameras && data.cameras.length > 0) {
          setCameras(data.cameras);
          setSelectedCam((prev) => {
            // Keep user selection if it still exists in returned cameras
            if (prev !== null && prev !== undefined && data.cameras.some(c => c.index === prev)) {
              return prev;
            }
            // Auto-prefer external USB camera if connected
            const usbCam = data.cameras.find(c =>
              c.name.toLowerCase().includes('usb') ||
              (c.tag && c.tag.toLowerCase().includes('usb'))
            );
            if (usbCam) return usbCam.index;
            if (data.default_index !== undefined) return data.default_index;
            return data.cameras[0].index;
          });
        }
      }
    } catch (e) {
      console.error('Failed to fetch cameras:', e);
    } finally {
      setLoadingCams(false);
    }
  };

  useEffect(() => {
    if (backendOnline) {
      fetchCameras();
    }
  }, [backendOnline]);

  const handleCameraChange = async (newIdx) => {
    const idxNum = Number(newIdx);
    setSelectedCam(idxNum);
    setError('');

    // If the pipeline is currently running with webcam, smoothly switch the backend camera
    if (running && source === 'webcam') {
      setLoading(true);
      try {
        const resp = await fetch(`${BACKEND_BASE}/api/video/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source: 'webcam',
            camera_index: idxNum,
            url: '',
          }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Failed to switch camera');
        setRunning(true);
        onSourceChanged?.('webcam', true);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
  };

  const startProcessing = async () => {
    if (!backendOnline) {
      setError('Backend is offline. Start backend/server.py first.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      let resp;
      if (source === 'upload' && uploadedFile) {
        const fd = new FormData();
        fd.append('file', uploadedFile);
        resp = await fetch(`${BACKEND_BASE}/api/video/upload`, { method: 'POST', body: fd });
      } else {
        resp = await fetch(`${BACKEND_BASE}/api/video/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source,
            camera_index: selectedCam,
            url: source === 'espcam' ? espcamUrl : '',
          }),
        });
      }
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Start failed');
      setRunning(true);
      onSourceChanged?.(source, true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const stopProcessing = async () => {
    setLoading(true);
    try {
      await fetch(`${BACKEND_BASE}/api/video/stop`, { method: 'POST' });
      setRunning(false);
      onSourceChanged?.(source, false);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0] || e.target?.files?.[0];
    if (file) {
      setUploadedFile(file);
      setSource('upload');
      setError('');
    }
  };

  const SOURCE_TABS = [
    { id: 'webcam',  icon: <Video className="w-3.5 h-3.5" />,  label: 'Webcam'   },
    { id: 'espcam',  icon: <Radio className="w-3.5 h-3.5" />,  label: 'ESP-CAM'  },
    { id: 'upload',  icon: <Upload className="w-3.5 h-3.5" />, label: 'Upload'   },
  ];

  return (
    <div className="glass-panel rounded-2xl p-4 border border-borderblue bg-cardbg flex flex-col gap-3 shadow-lg h-full">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-borderblue pb-2">
        <Video className="w-4 h-4 text-primaryaccent" />
        <span className="text-xs font-bold text-textlight font-mono">VIDEO INPUT SOURCE</span>
        <span className={`ml-auto text-[9px] font-mono font-bold px-2 py-0.5 rounded border ${
          backendOnline
            ? 'text-green-400 border-green-400/30 bg-green-400/10'
            : 'text-red-400 border-red-400/30 bg-red-400/10'
        }`}>
          {backendOnline ? '● BACKEND ONLINE' : '● OFFLINE'}
        </span>
      </div>

      {/* Source selector tabs */}
      <div className="grid grid-cols-3 gap-1.5">
        {SOURCE_TABS.map(({ id, icon, label }) => (
          <button
            key={id}
            onClick={() => { setSource(id); setError(''); }}
            disabled={running}
            className={`flex items-center justify-center gap-1.5 py-2 rounded-xl text-[10px] font-bold font-mono border transition-all ${
              source === id
                ? 'active-nav-gradient border-primaryaccent text-white'
                : 'bg-white/5 border-white/10 text-slate-400 hover:border-borderblue hover:bg-cardhover'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {icon} {label}
          </button>
        ))}
      </div>

      {/* Source-specific config */}
      <div className="flex flex-col gap-2">
        {source === 'webcam' && (
          <div className="bg-white/5 rounded-xl p-3 border border-white/10 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[9px] font-mono text-slate-400 font-bold uppercase tracking-wider">
                <Video className="w-3 h-3 text-primaryaccent" />
                <span>Camera Input Device</span>
              </div>
              <button
                onClick={fetchCameras}
                disabled={loadingCams || running}
                className="flex items-center gap-1 text-[9px] font-mono text-cyan-400 hover:text-cyan-300 disabled:opacity-40 transition-colors cursor-pointer"
                title="Scan for connected cameras"
              >
                <RefreshCw className={`w-2.5 h-2.5 ${loadingCams ? 'animate-spin' : ''}`} />
                <span>{loadingCams ? 'Scanning...' : 'Scan'}</span>
              </button>
            </div>

            {cameras.length > 0 ? (
              <div className="flex flex-col gap-2">
                {/* One-click camera switch pill buttons */}
                <div className="grid grid-cols-2 gap-1.5">
                  {cameras.map((cam) => {
                    const isUsb = cam.name.toLowerCase().includes('usb') || (cam.tag && cam.tag.toLowerCase().includes('usb'));
                    const isSelected = selectedCam === cam.index;
                    return (
                      <button
                        key={cam.index}
                        type="button"
                        onClick={() => handleCameraChange(cam.index)}
                        disabled={loading}
                        className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-[9px] font-mono font-bold border transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-sm shadow-cyan-500/20'
                            : 'bg-white/5 border-white/10 text-slate-400 hover:border-slate-500 hover:bg-white/10'
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                        title={cam.label}
                      >
                        <span>{isUsb ? '🔌' : '💻'}</span>
                        <span className="truncate">{isUsb ? 'External USB' : 'Laptop Cam'}</span>
                        <span className={`text-[8px] px-1 py-0.2 rounded ${isSelected ? 'bg-cyan-400/30 text-cyan-200' : 'bg-white/10 text-slate-500'}`}>
                          #{cam.index}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* Dropdown with full details */}
                <select
                  value={selectedCam}
                  onChange={(e) => handleCameraChange(Number(e.target.value))}
                  disabled={loading}
                  className="w-full bg-darkbg border border-borderblue rounded-lg px-2.5 py-1.5 text-[10px] font-mono text-slate-200 focus:outline-none focus:border-primaryaccent disabled:opacity-50 cursor-pointer"
                >
                  {cameras.map((cam) => (
                    <option key={cam.index} value={cam.index} className="bg-slate-900 text-slate-200">
                      📷 {cam.label || `Camera ${cam.index}`}
                    </option>
                  ))}
                </select>

                <div className="flex items-center justify-between text-[8px] font-mono text-slate-400 px-0.5">
                  <span>Selected: <span className="text-cyan-300 font-bold">Index {selectedCam} ({cameras.find(c => c.index === selectedCam)?.tag || cameras.find(c => c.index === selectedCam)?.name || 'Camera'})</span></span>
                  <span className="text-emerald-400 font-bold">● {cameras.length} camera(s) detected</span>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                <span>Default Webcam (index {selectedCam})</span>
                <button
                  onClick={fetchCameras}
                  className="text-[9px] text-cyan-400 underline cursor-pointer"
                >
                  Click to detect
                </button>
              </div>
            )}
          </div>
        )}

        {source === 'espcam' && (
          <div className="flex flex-col gap-1.5">
            <label className="text-[9px] font-mono text-slate-400 font-bold uppercase">
              ESP32-CAM MJPEG Stream URL
            </label>
            <input
              type="text"
              value={espcamUrl}
              onChange={(e) => setEspcamUrl(e.target.value)}
              disabled={running}
              placeholder="http://192.168.4.2/stream"
              className="w-full bg-darkbg border border-borderblue rounded-lg px-3 py-2 text-[10px] font-mono text-slate-200 focus:outline-none focus:border-primaryaccent disabled:opacity-50"
            />
          </div>
        )}

        {source === 'upload' && (
          <div
            className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-all ${
              dragOver
                ? 'border-primaryaccent bg-primaryaccent/10'
                : 'border-white/20 hover:border-borderblue bg-white/5'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            onClick={() => fileRef.current?.click()}
          >
            <input
              ref={fileRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={handleFileDrop}
            />
            {uploadedFile ? (
              <div className="flex flex-col items-center gap-1">
                <CheckCircle className="w-6 h-6 text-green-400" />
                <span className="text-[10px] font-mono text-green-400 font-bold truncate max-w-[160px]">
                  {uploadedFile.name}
                </span>
                <span className="text-[9px] text-slate-500">
                  {(uploadedFile.size / 1024 / 1024).toFixed(1)} MB
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-1.5">
                <Upload className="w-6 h-6 text-slate-500" />
                <span className="text-[10px] font-mono text-slate-400">
                  Drop video file or click to browse
                </span>
                <span className="text-[9px] text-slate-600">MP4, AVI, MOV supported</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 bg-red-900/20 border border-red-500/30 rounded-lg p-2">
          <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
          <span className="text-[9px] font-mono text-red-400">{error}</span>
        </div>
      )}

      {/* Start/Stop button */}
      <button
        onClick={running ? stopProcessing : startProcessing}
        disabled={loading || (!backendOnline && !running) || (source === 'upload' && !uploadedFile && !running)}
        className={`mt-auto w-full py-2.5 rounded-xl font-bold font-mono text-xs flex items-center justify-center gap-2 transition-all border disabled:opacity-40 disabled:cursor-not-allowed ${
          running
            ? 'bg-red-600/20 border-red-500/50 text-red-400 hover:bg-red-600/30'
            : 'primary-btn-gradient border-primaryaccent text-white hover:opacity-90 active:scale-95'
        }`}
      >
        {loading ? (
          <><Loader className="w-3.5 h-3.5 animate-spin" /> Processing…</>
        ) : running ? (
          <><Square className="w-3.5 h-3.5" /> Stop Pipeline</>
        ) : (
          <><Play className="w-3.5 h-3.5" /> Start Pipeline</>
        )}
      </button>

      {running && (
        <div className="flex items-center gap-2 text-[9px] font-mono text-green-400 animate-pulse">
          <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
          Pipeline running — {source.toUpperCase()} source active
        </div>
      )}
    </div>
  );
}
