import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix default leaflet marker icon asset issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

export default function IndiaAqiMap({ places = [], onSelectPlace = null }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);
  const navigate = useNavigate();

  // Initialize Map Once
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [22.5937, 78.9629],
        zoom: 5,
        minZoom: 4,
        maxZoom: 12,
        scrollWheelZoom: true,
      });

      // OpenStreetMap standard tiles - 100% free, no API key required, zero watermarks
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18,
      }).addTo(map);

      const markersGroup = L.layerGroup().addTo(map);
      markersLayerRef.current = markersGroup;
      mapInstanceRef.current = map;
    }

    return () => {
      // Cleanup on unmount
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Markers whenever `places` data updates
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();

    places.forEach((p) => {
      if (!p.lat || !p.lon) return;

      const aqiNum = p.aqi ?? "--";
      const aqiColor = p.color || "#1E9E57";

      // Custom Circular AQI Bubble HTML Marker (matching reference image)
      const customIcon = L.divIcon({
        className: "custom-aqi-bubble-wrapper",
        html: `
          <div style="
            background-color: ${aqiColor};
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: 800;
            font-size: 13px;
            box-shadow: 0 3px 8px rgba(0,0,0,0.35);
            border: 2px solid #ffffff;
            cursor: pointer;
            transition: transform 0.15s ease-in-out;
          " onmouseover="this.style.transform='scale(1.25)'" onmouseout="this.style.transform='scale(1)'">
            ${aqiNum}
          </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });

      const marker = L.marker([p.lat, p.lon], { icon: customIcon });

      // Rich Interactive Popup
      const popupContent = `
        <div style="font-family: inherit; min-width: 180px; padding: 4px;">
          <div style="display: flex; justify-content: space-between; align-items: start; gap: 8px;">
            <div>
              <div style="font-weight: 800; font-size: 15px; color: #111827;">${p.name}</div>
              <div style="font-size: 11px; color: #6B7280; text-transform: uppercase;">${p.state || ""}</div>
            </div>
            <div style="background-color: ${aqiColor}; color: #fff; font-weight: 800; padding: 2px 8px; border-radius: 9999px; font-size: 12px;">
              AQI ${aqiNum}
            </div>
          </div>
          <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid #E5E7EB; font-size: 11px; color: #374151;">
            <div><strong>Status:</strong> ${p.label || "No data"}</div>
            <div><strong>Source:</strong> ${p.has_ground_station ? "📡 Ground Station" : "🛰️ Atmospheric Grid"}</div>
          </div>
          <button id="view-place-${p.id}" style="
            margin-top: 8px;
            width: 100%;
            background-color: #059669;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
          ">
            View 5-Day Forecast & Trends →
          </button>
        </div>
      `;

      marker.bindPopup(popupContent);

      marker.on("popupopen", () => {
        const btn = document.getElementById(`view-place-${p.id}`);
        if (btn) {
          btn.onclick = () => {
            if (onSelectPlace) {
              onSelectPlace(p);
            } else {
              navigate(`/place/${p.id}`);
            }
          };
        }
      });

      marker.on("click", () => {
        if (onSelectPlace) {
          onSelectPlace(p);
        }
      });

      markersLayerRef.current.addLayer(marker);
    });
  }, [places, navigate, onSelectPlace]);

  // Quick Region Zoom Handlers
  const zoomToRegion = (lat, lon, zoom) => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([lat, lon], zoom, { duration: 1.2 });
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
      {/* Map Header & Controls */}
      <div className="p-4 border-b border-gray-200 bg-gray-50 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">🗺️</span>
          <div>
            <h2 className="text-base font-extrabold text-gray-900">
              Interactive India AQI Station Map
            </h2>
            <p className="text-xs text-gray-500">
              Live CPCB colored pins with real-time AQI readings across all States & UTs
            </p>
          </div>
        </div>

        {/* Quick Region Switcher */}
        <div className="flex flex-wrap gap-1.5 text-xs">
          <button
            onClick={() => zoomToRegion(22.5937, 78.9629, 5)}
            className="px-2.5 py-1 rounded-md bg-white border border-gray-300 hover:border-emerald-500 font-medium text-gray-700 transition"
          >
            🇮🇳 All India
          </button>
          <button
            onClick={() => zoomToRegion(30.73, 76.78, 8)}
            className="px-2.5 py-1 rounded-md bg-white border border-gray-300 hover:border-emerald-500 font-medium text-gray-700 transition"
          >
            📍 Punjab & Tricity (Mohali/Kharar)
          </button>
          <button
            onClick={() => zoomToRegion(28.61, 77.21, 8)}
            className="px-2.5 py-1 rounded-md bg-white border border-gray-300 hover:border-emerald-500 font-medium text-gray-700 transition"
          >
            📍 Delhi NCR
          </button>
          <button
            onClick={() => zoomToRegion(19.07, 72.87, 8)}
            className="px-2.5 py-1 rounded-md bg-white border border-gray-300 hover:border-emerald-500 font-medium text-gray-700 transition"
          >
            📍 Mumbai
          </button>
          <button
            onClick={() => zoomToRegion(12.97, 77.59, 8)}
            className="px-2.5 py-1 rounded-md bg-white border border-gray-300 hover:border-emerald-500 font-medium text-gray-700 transition"
          >
            📍 Bengaluru
          </button>
        </div>
      </div>

      {/* Map Canvas */}
      <div
        ref={mapContainerRef}
        className="w-full h-[520px] sm:h-[600px] z-10"
        style={{ background: "#e5e7eb" }}
      />
    </div>
  );
}
