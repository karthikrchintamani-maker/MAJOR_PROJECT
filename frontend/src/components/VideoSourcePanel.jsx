import React, { useState, useRef } from 'react';
import {
  Video, Webcam, Radio, Upload, Play, Square,
  Link, CheckCircle, XCircle, Loader, AlertTriangle
} from 'lucide-react';

const BACKEND_BASE = 'http://localhost:5001';

export default function VideoSourcePanel({ onSourceChanged, backendOnline }) {
  const [source, setSource] = useState('webcam');   // 'webcam'|'espcam'|'upload'
  const [espcamUrl, setEspcamUrl] = useState('http://192.168.4.2/stream');
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

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
          <div className="bg-white/5 rounded-xl p-3 border border-white/10">
            <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
              <Video className="w-3.5 h-3.5 text-primaryaccent" />
              <span>Using system default webcam (index 0)</span>
            </div>
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
