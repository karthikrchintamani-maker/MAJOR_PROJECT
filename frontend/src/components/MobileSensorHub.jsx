import React from 'react';
import {
  Smartphone, Activity, Wifi, Battery, BatteryCharging, Compass, Radio,
  Gauge, Zap, Thermometer, ShieldAlert, Volume2, Sun, Navigation, Eye, CheckCircle2, XCircle
} from 'lucide-react';

export default function MobileSensorHub({ mobileIot, mobileActive, mobileHz }) {
  const data = mobileIot;
  const isOnline = Boolean(mobileActive && data);

  const sensors = data?.sensors || {};
  const health = data?.device_health || {};
  const road = data?.road_intelligence || {};
  const obd = data?.obd2 || {};
  const gps = sensors.gps || {};
  const accel = sensors.accel || {};
  const gyro = sensors.gyro || {};
  const linAcc = sensors.linear_accel || {};
  const orient = sensors.orientation || {};
  const baro = sensors.barometer || {};
  const light = sensors.ambient_light || {};
  const prox = sensors.proximity || {};
  const audio = sensors.audio || {};

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Top Mobile Node Status Header */}
      <div className="glass-panel p-3.5 rounded-2xl border border-borderblue bg-cardbg shadow-lg flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg shadow-md ${
            isOnline ? 'bg-cyan-500/20 text-[#00E5FF] border border-[#00E5FF]/40 animate-pulse' : 'bg-slate-800 text-slate-500 border border-slate-700'
          }`}>
            <Smartphone className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-extrabold text-textlight tracking-wide font-mono">
                {data?.device_id || 'Android Mobile Sensor Node (Kotlin)'}
              </h3>
              <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold font-mono border ${
                isOnline 
                  ? 'bg-[#22C55E]/15 text-[#22C55E] border-[#22C55E]/30' 
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
              }`}>
                {isOnline ? 'LIVE UDP STREAM' : 'WAITING FOR PACKETS'}
              </span>
            </div>
            <p className="text-[11px] text-textgrey font-mono mt-0.5">
              Protocol: <span className="text-cyan-400">UDP Port 5005 (UTF-8 JSON)</span> • Seq: <span className="text-textlight font-bold">#{data?.seq ?? '—'}</span> • Stream: <span className="text-green-400 font-bold">{mobileHz || data?.stream_hz || 0} Hz</span>
            </p>
          </div>
        </div>

        {/* CRC32 & Health Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-black/40 border border-borderblue text-xs font-mono">
            <span className="text-textgrey text-[10px]">CRC-32:</span>
            <span className="text-slate-300 font-bold">{data?.crc32 || '—'}</span>
            {data?.crc32 && (
              data.crc_match ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-[#22C55E]" title="CRC-32 Validated" />
              ) : (
                <XCircle className="w-3.5 h-3.5 text-[#FF3B4D]" title="CRC-32 Check Failed" />
              )
            )}
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-black/40 border border-borderblue text-xs font-mono">
            {health.charging ? <BatteryCharging className="w-4 h-4 text-green-400" /> : <Battery className="w-4 h-4 text-cyan-400" />}
            <span className="text-textlight font-bold">{health.battery_pct ?? '—'}%</span>
            <span className="text-textgrey text-[10px]">({health.battery_temp_c ?? '—'}°C)</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-black/40 border border-borderblue text-xs font-mono">
            <Wifi className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-textlight font-bold">{health.wifi_rssi_dbm ?? '—'} dBm</span>
          </div>
        </div>
      </div>

      {/* Grid: Road Intelligence & Telemetry Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Road Intelligence Card */}
        <div className="glass-panel p-3.5 rounded-2xl border border-borderblue bg-cardbg shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between pb-2 border-b border-white/5">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#FF9F1C]" />
              <span className="text-xs font-bold font-mono text-textlight uppercase tracking-wider">ROAD INTELLIGENCE</span>
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
              road.impact_detected 
                ? 'bg-[#FF3B4D]/20 text-[#FF3B4D] border-[#FF3B4D]/40 animate-pulse'
                : 'bg-[#22C55E]/10 text-[#22C55E] border-[#22C55E]/20'
            }`}>
              {road.impact_detected ? 'IMPACT DETECTED' : 'SURFACE: ' + (road.surface_class || 'NOMINAL')}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 my-2">
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5">
              <span className="text-[10px] text-textgrey font-mono block">CONDITION SCORE</span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-2xl font-black font-mono text-cyan-300">{road.condition_score ?? '—'}</span>
                <span className="text-[10px] text-textgrey font-mono">/100</span>
              </div>
            </div>
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5">
              <span className="text-[10px] text-textgrey font-mono block">VIBRATION RMS</span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-2xl font-black font-mono text-amber-300">
                  {typeof road.vibration_rms === 'number' ? road.vibration_rms.toFixed(3) : '—'}
                </span>
                <span className="text-[10px] text-textgrey font-mono">m/s²</span>
              </div>
            </div>
          </div>

          <div className="text-[11px] font-mono text-textgrey flex items-center justify-between px-1">
            <span>Surface Quality Metric:</span>
            <span className="font-bold text-textlight">{road.surface_class || 'SMOOTH'}</span>
          </div>
        </div>

        {/* Vehicle OBD-II Engine Metrics */}
        <div className="glass-panel p-3.5 rounded-2xl border border-borderblue bg-cardbg shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between pb-2 border-b border-white/5">
            <div className="flex items-center gap-2">
              <Gauge className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold font-mono text-textlight uppercase tracking-wider">OBD-II CAN-BUS</span>
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
              obd.connected 
                ? 'bg-[#22C55E]/10 text-[#22C55E] border-[#22C55E]/20' 
                : 'bg-slate-700/50 text-slate-400 border-slate-600'
            }`}>
              {obd.connected ? 'CAN CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 my-2">
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5">
              <span className="text-[10px] text-textgrey font-mono block">VEHICLE SPEED</span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-2xl font-black font-mono text-[#00E5FF]">{obd.speed_kmh ?? '—'}</span>
                <span className="text-[10px] text-[#00E5FF] font-mono">KM/H</span>
              </div>
            </div>
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5">
              <span className="text-[10px] text-textgrey font-mono block">ENGINE RPM</span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-2xl font-black font-mono text-emerald-400">{obd.rpm ?? '—'}</span>
                <span className="text-[10px] text-emerald-400 font-mono">RPM</span>
              </div>
            </div>
          </div>

          <div className="text-[10px] font-mono text-textgrey grid grid-cols-3 gap-1 text-center bg-black/20 p-1.5 rounded-lg border border-white/5">
            <div>Throttle: <span className="text-textlight font-bold">{obd.throttle_pos ?? '—'}%</span></div>
            <div>Coolant: <span className="text-textlight font-bold">{obd.coolant_temp_c ?? '—'}°C</span></div>
            <div>Load: <span className="text-textlight font-bold">{obd.engine_load ?? '—'}%</span></div>
          </div>
        </div>

        {/* GPS & Spatial Kinematics */}
        <div className="glass-panel p-3.5 rounded-2xl border border-borderblue bg-cardbg shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between pb-2 border-b border-white/5">
            <div className="flex items-center gap-2">
              <Navigation className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold font-mono text-textlight uppercase tracking-wider">MOBILE GNSS / GPS</span>
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
              gps.has_fix ? 'bg-[#22C55E]/10 text-[#22C55E] border-[#22C55E]/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
            }`}>
              {gps.has_fix ? '3D FIX (±' + (gps.accuracy_m?.toFixed(1) || '—') + 'm)' : 'NO FIX'}
            </span>
          </div>

          <div className="my-2 p-2.5 rounded-xl bg-black/30 border border-white/5 font-mono text-xs">
            <div className="flex justify-between py-0.5">
              <span className="text-textgrey">Latitude:</span>
              <span className="text-textlight font-bold">{typeof gps.lat === 'number' ? gps.lat.toFixed(6) : '—'}</span>
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-textgrey">Longitude:</span>
              <span className="text-textlight font-bold">{typeof gps.lng === 'number' ? gps.lng.toFixed(6) : '—'}</span>
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-textgrey">Altitude:</span>
              <span className="text-textlight font-bold">{typeof gps.altitude_m === 'number' ? gps.altitude_m.toFixed(1) + ' m' : '—'}</span>
            </div>
          </div>

          <div className="text-[10px] font-mono text-textgrey flex items-center justify-between px-1">
            <span>Speed: <strong className="text-textlight">{typeof gps.speed_mps === 'number' ? (gps.speed_mps * 3.6).toFixed(1) : '—'} km/h</strong></span>
            <span>Bearing: <strong className="text-textlight">{typeof gps.bearing === 'number' ? gps.bearing.toFixed(1) + '°' : '—'}</strong></span>
          </div>
        </div>
      </div>

      {/* Detailed Sensor Matrix: IMU, Orientation, Environment, Acoustics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* IMU & Kinematics */}
        <div className="glass-panel p-3.5 rounded-2xl border border-borderblue bg-cardbg shadow-lg flex flex-col gap-2.5">
          <div className="flex items-center justify-between border-b border-white/5 pb-2">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold font-mono text-textlight uppercase tracking-wider">TRI-AXIAL IMU & ORIENTATION</span>
            </div>
            <span className="text-[10px] font-mono text-cyan-300">50 Hz MEMS</span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
            {/* Accel */}
            <div className="p-2 rounded-xl bg-black/30 border border-white/5">
              <span className="text-[9px] text-textgrey block mb-1">ACCEL (m/s²)</span>
              <div className="text-[11px] font-bold text-slate-200">X: {accel.x?.toFixed(2) ?? '—'}</div>
              <div className="text-[11px] font-bold text-slate-200">Y: {accel.y?.toFixed(2) ?? '—'}</div>
              <div className="text-[11px] font-bold text-slate-200">Z: {accel.z?.toFixed(2) ?? '—'}</div>
            </div>

            {/* Gyro */}
            <div className="p-2 rounded-xl bg-black/30 border border-white/5">
              <span className="text-[9px] text-textgrey block mb-1">GYROSCOPE (rad/s)</span>
              <div className="text-[11px] font-bold text-emerald-400">X: {gyro.x?.toFixed(3) ?? '—'}</div>
              <div className="text-[11px] font-bold text-emerald-400">Y: {gyro.y?.toFixed(3) ?? '—'}</div>
              <div className="text-[11px] font-bold text-emerald-400">Z: {gyro.z?.toFixed(3) ?? '—'}</div>
            </div>

            {/* Orientation */}
            <div className="p-2 rounded-xl bg-black/30 border border-white/5">
              <span className="text-[9px] text-textgrey block mb-1">ORIENTATION</span>
              <div className="text-[11px] font-bold text-amber-300">P: {orient.pitch_deg?.toFixed(1) ?? '—'}°</div>
              <div className="text-[11px] font-bold text-amber-300">R: {orient.roll_deg?.toFixed(1) ?? '—'}°</div>
              <div className="text-[11px] font-bold text-amber-300">Y: {orient.yaw_deg?.toFixed(1) ?? '—'}°</div>
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] font-mono text-textgrey bg-black/20 p-2 rounded-xl border border-white/5">
            <span>Linear Accel: <strong className="text-textlight">{linAcc.x?.toFixed(2) ?? '—'}, {linAcc.y?.toFixed(2) ?? '—'}, {linAcc.z?.toFixed(2) ?? '—'}</strong></span>
            <span>Thermal: <strong className="text-cyan-300 font-bold">{data?.thermal_status || 'NOMINAL'}</strong></span>
          </div>
        </div>

        {/* Environmental & Acoustic Sensors */}
        <div className="glass-panel p-3.5 rounded-2xl border border-borderblue bg-cardbg shadow-lg flex flex-col gap-2.5">
          <div className="flex items-center justify-between border-b border-white/5 pb-2">
            <div className="flex items-center gap-2">
              <Sun className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-bold font-mono text-textlight uppercase tracking-wider">ENVIRONMENT & ACOUSTIC SENSORS</span>
            </div>
            <span className="text-[10px] font-mono text-textgrey">Mobile Peripherals</span>
          </div>

          <div className="grid grid-cols-2 gap-2 font-mono text-xs">
            {/* Barometer */}
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5 flex flex-col justify-between">
              <span className="text-[10px] text-textgrey block">BAROMETER & PRESSURE</span>
              <div className="my-1">
                <span className="text-lg font-bold text-purple-300">{baro.pressure_hpa?.toFixed(1) ?? '—'}</span>
                <span className="text-[10px] text-textgrey ml-1">hPa</span>
              </div>
              <span className="text-[10px] text-textgrey">Rel Alt: <strong className="text-textlight">{baro.rel_altitude_m?.toFixed(1) ?? '—'} m</strong></span>
            </div>

            {/* Ambient Light */}
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5 flex flex-col justify-between">
              <span className="text-[10px] text-textgrey block">AMBIENT LIGHT</span>
              <div className="my-1">
                <span className="text-lg font-bold text-yellow-300">{light.lux?.toFixed(0) ?? '—'}</span>
                <span className="text-[10px] text-textgrey ml-1">LUX</span>
              </div>
              <span className="text-[10px] text-textgrey">Condition: <strong className="text-textlight">{light.condition || 'DAYLIGHT'}</strong></span>
            </div>

            {/* Proximity */}
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5 flex flex-col justify-between">
              <span className="text-[10px] text-textgrey block">PROXIMITY</span>
              <div className="my-1">
                <span className="text-lg font-bold text-cyan-300">{prox.distance_cm?.toFixed(1) ?? '—'}</span>
                <span className="text-[10px] text-textgrey ml-1">cm</span>
              </div>
              <span className="text-[10px] text-textgrey">State: <strong className="text-textlight">{prox.is_near ? 'NEAR (OBJECT)' : 'CLEAR'}</strong></span>
            </div>

            {/* Audio Acoustic */}
            <div className="p-2.5 rounded-xl bg-black/30 border border-white/5 flex flex-col justify-between">
              <span className="text-[10px] text-textgrey block">ACOUSTIC AUDIO RMS</span>
              <div className="my-1">
                <span className="text-lg font-bold text-rose-400">{audio.rms_dbfs?.toFixed(1) ?? '—'}</span>
                <span className="text-[10px] text-textgrey ml-1">dBFS</span>
              </div>
              <span className="text-[10px] text-textgrey">ZCR: <strong className="text-textlight">{audio.zcr_hz?.toFixed(0) ?? '—'} Hz</strong></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
