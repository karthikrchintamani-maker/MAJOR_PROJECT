import React, { useEffect } from 'react';
import { MapPin, Compass, Navigation } from 'lucide-react';
import { MapContainer, TileLayer, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Pulsing cyan dot icon for the vehicle (matching #00E5FF secondary accent)
const carIcon = new L.DivIcon({
  className: 'custom-car-icon',
  html: `<div class="relative flex h-4 w-4">
    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00E5FF] opacity-75"></span>
    <span class="relative inline-flex rounded-full h-4 w-4 bg-[#00E5FF] border border-white"></span>
  </div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8]
});

function RecenterMap({ lat, lng }) {
  const map = useMap();
  useEffect(() => {
    if (lat && lng) {
      map.panTo([lat, lng]);
    }
  }, [lat, lng, map]);
  return null;
}

export default function GpsMap({ lat = 13.05005, lng = 77.71700, activeScenario, onUpdateLocation }) {
  const defaultCenter = [lat || 13.05005, lng || 77.71700]; // East Point College of Engineering & Technology (Jnana Prabha Campus, Avalahalli)

  const scenarioLabels = {
    highway: 'OLD MADRAS RD / NH-75',
    city: 'EAST POINT CAMPUS (EPCET)',
    pothole: 'HIRANDAHALLI - AVALAHALLI RD',
    emergency: 'EAST POINT HOSPITAL SOS',
  };

  const handleLocateMe = () => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          if (onUpdateLocation) {
            onUpdateLocation(pos.coords.latitude, pos.coords.longitude);
          }
        },
        (err) => {
          console.warn('Geolocation error:', err.message);
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-3 border border-borderblue shadow-lg bg-cardbg flex flex-col gap-2 h-full min-h-0">
      <div className="flex items-center justify-between border-b border-borderblue pb-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-textlight">
          <MapPin className="w-4.5 h-4.5 text-[#00A8FF]" />
          <span>NEO-6M GPS REAL-TIME VEHICLE TRACKING</span>
        </div>
        <div className="flex items-center gap-2">
          {onUpdateLocation && (
            <button
              onClick={handleLocateMe}
              title="Detect Current Device GPS Location (Bangalore)"
              className="flex items-center gap-1 text-[9px] font-mono text-[#00E5FF] hover:bg-[#00E5FF]/10 px-1.5 py-0.5 rounded border border-[#00E5FF]/30 transition-all"
            >
              <Navigation className="w-3 h-3" /> LOCATE
            </button>
          )}
          <span className="text-[9px] font-mono font-bold text-[#22C55E] bg-[#22C55E]/10 px-1.5 py-0.5 rounded border border-[#22C55E]/20 animate-pulse">
            LIVE
          </span>
          <span className="text-[10px] font-mono text-textgrey">
            {scenarioLabels[activeScenario] || 'BENGALURU CORRIDOR'}
          </span>
        </div>
      </div>

      <div className="relative flex-1 rounded-xl overflow-hidden bg-slate-950 border border-borderblue z-10">
        <MapContainer 
          center={defaultCenter} 
          zoom={16} 
          scrollWheelZoom={false}
          zoomControl={false}
          className="w-full h-full"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />
          <Marker position={[lat, lng]} icon={carIcon} />
          <RecenterMap lat={lat} lng={lng} />
        </MapContainer>

        <div className="absolute bottom-3 left-3 z-[1000] bg-black/85 backdrop-blur border border-slate-800 px-3 py-1 rounded font-mono text-[9px] text-[#00E5FF]">
          LAT: {lat.toFixed(5)} | LNG: {lng.toFixed(5)}
        </div>

        <div className="absolute bottom-3 right-3 z-[1000] bg-black/85 backdrop-blur border border-slate-800 px-3 py-1 rounded font-mono text-[9px] text-[#22C55E] flex items-center gap-1.5">
          <Compass className="w-3.5 h-3.5" /> HEADING: 042° NE
        </div>
      </div>
    </div>
  );
}
