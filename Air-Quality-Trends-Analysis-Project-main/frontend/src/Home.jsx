import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";
import Header from "./components/Header";
import IndiaAqiMap from "./components/IndiaAqiMap";
import AiAssistantModal from "./components/AiAssistantModal";

const API = import.meta.env.VITE_API_BASE ?? "";

const CPCB_SCALE = [
  { label: "Good", range: "0 - 50", color: "#1E9E57", desc: "Minimal impact" },
  { label: "Satisfactory", range: "51 - 100", color: "#8BC34A", desc: "Minor breathing discomfort to sensitive people" },
  { label: "Moderate", range: "101 - 200", color: "#F4C20D", desc: "Breathing discomfort to people with lung/heart disease" },
  { label: "Poor", range: "201 - 300", color: "#F28C28", desc: "Breathing discomfort to most people on prolonged exposure" },
  { label: "Very Poor", range: "301 - 400", color: "#D32F2F", desc: "Respiratory illness to people on prolonged exposure" },
  { label: "Severe", range: "401 - 500", color: "#7B1113", desc: "Affects healthy people and seriously impacts sensitive groups" },
];

function formatDataAge(minutes) {
  if (minutes == null) return "Live";
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatAgeWarning(minutes, warning) {
  if (warning) return warning;
  if (!minutes || minutes <= 30) return null;
  if (minutes < 60) return `Data is ${minutes}m old (>30 min delay)`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Data is ${hours}h old (station feed delayed)`;
  const days = Math.floor(hours / 24);
  return `Station delayed (${days} days old • CPCB baseline)`;
}

export default function Home() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [featuredStations, setFeaturedStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedState, setSelectedState] = useState(null);
  const [inspectPlace, setInspectPlace] = useState(null);

  const fetchData = async () => {
    setError(null);
    try {
      const [summaryRes, featuredRes] = await Promise.all([
        axios.get(`${API}/map/summary`),
        axios.get(`${API}/places/featured/forecasts`),
      ]);
      setData(summaryRes.data);
      setFeaturedStations(featuredRes.data.featured || []);
    } catch (err) {
      console.error("Failed to fetch map data:", err);
      setError("Unable to connect to the AirSense API. Ensure the backend server is running.");
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 60 seconds
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      fetchData();
    }, 60000); // 60 seconds
    return () => clearInterval(interval);
  }, []);

  const states = data?.states || [];
  const places = data?.places || [];

  const filteredStates = states.filter((s) =>
    s.state.toLowerCase().includes(search.toLowerCase())
  );

  const filteredPlaces = places.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      (p.state && p.state.toLowerCase().includes(search.toLowerCase()))
  );

  const placesInSelectedState = selectedState
    ? places.filter((p) => p.state?.toLowerCase() === selectedState.toLowerCase())
    : [];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Hero & Search Banner */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 mb-8 shadow-sm">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 mb-3">
              <span>🇮🇳 Real-Time National CPCB Air Quality Network</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">
              India Air Quality Map & 5-Day AI Forecast
            </h1>
            <p className="mt-2 text-base text-gray-600">
              Live ground station sensors and satellite atmospheric models for all 36 States and Union Territories.
              Inspect live AQI bubbles, explore subdistrict stations, and view upcoming 5-day predictive trends.
            </p>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (filteredPlaces.length === 1) {
                navigate(`/place/${filteredPlaces[0].id}`);
              } else if (search.trim()) {
                navigate(`/search?q=${encodeURIComponent(search.trim())}`);
              }
            }}
            className="mt-6 flex flex-col sm:flex-row gap-3"
          >
            <div className="relative flex-1">
              <input
                type="text"
                placeholder="Search any state or city (e.g. Delhi, Mohali, Kharar, Mumbai, Chandigarh)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full px-4 py-3 pl-11 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 bg-white text-gray-900 placeholder-gray-400 text-sm shadow-sm"
              />
              <span className="absolute left-4 top-3.5 text-gray-400 text-lg">🔍</span>
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-3 top-3 text-xs text-gray-400 hover:text-gray-600 bg-gray-100 px-2 py-1 rounded-md"
                >
                  Clear
                </button>
              )}

              {/* Instant Search Suggestions Dropdown */}
              {search.trim().length > 0 && filteredPlaces.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden divide-y divide-gray-100 max-h-72 overflow-y-auto">
                  {filteredPlaces.slice(0, 6).map((p) => {
                    const aqiColor = p.color || (p.aqi != null ? "#1E9E57" : "#BDBDBD");
                    return (
                      <div
                        key={p.id}
                        onClick={() => navigate(`/place/${p.id}`)}
                        className="p-3 hover:bg-emerald-50 cursor-pointer flex items-center justify-between transition"
                      >
                        <div>
                          <span className="font-bold text-sm text-gray-900">{p.name}</span>
                          <span className="text-xs text-gray-500 ml-2">({p.state})</span>
                          <div className="text-[11px] text-gray-600 truncate max-w-xs sm:max-w-md">
                            📡 {p.station_name || "Continuous Ambient Air Station"}
                          </div>
                        </div>
                        <div
                          className="px-2 py-0.5 rounded-full text-xs font-bold text-white shadow-xs"
                          style={{ backgroundColor: aqiColor }}
                        >
                          {p.aqi != null ? `AQI ${p.aqi}` : "No data"}
                        </div>
                      </div>
                    );
                  })}
                  <div
                    onClick={() => navigate(`/search?q=${encodeURIComponent(search.trim())}`)}
                    className="p-2.5 bg-gray-50 hover:bg-emerald-100 cursor-pointer text-center text-xs font-semibold text-emerald-800 transition"
                  >
                    View all {filteredPlaces.length} matching stations in Search Directory →
                  </div>
                </div>
              )}
            </div>

            <button
              type="submit"
              className="px-5 py-3 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-sm font-bold shadow-sm transition"
            >
              Search
            </button>

            <Link
              to="/search"
              className="px-4 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-sm font-semibold text-center transition flex items-center justify-center gap-1"
            >
              <span>Directory</span>
              <span>→</span>
            </Link>

            {data?.as_of && (
              <div className="hidden lg:flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-xl border border-gray-200 text-xs text-gray-500">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>As of: {new Date(data.as_of).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} IST</span>
              </div>
            )}
          </form>
        </section>

        {/* IMMEDIATE SEARCH RESULTS (Displayed right below search bar when query is active) */}
        {!loading && !error && search.trim() !== "" && (
          <section className="mb-10 bg-white border-2 border-emerald-500/40 rounded-2xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  <span>Matching Stations for &ldquo;{search}&rdquo; ({filteredPlaces.length})</span>
                </h2>
                <p className="text-xs text-gray-500">
                  Click any city below to inspect live sensor telemetry and 5-day predictive trends
                </p>
              </div>
              <button
                onClick={() => setSearch("")}
                className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg font-medium transition"
              >
                ✕ Clear Search
              </button>
            </div>

            {filteredPlaces.length === 0 ? (
              <p className="text-gray-500 text-sm italic py-4">
                No matching cities found for &quot;{search}&quot;. Try searching for another city like Delhi, Mohali, Kharar, or Mumbai.
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {filteredPlaces.map((p) => {
                  const aqiColor = p.color || (p.aqi != null ? "#1E9E57" : "#BDBDBD");
                  return (
                    <button
                      key={p.id}
                      onClick={() => navigate(`/place/${p.id}`)}
                      className="bg-gray-50/60 p-4 rounded-xl border border-gray-200 hover:border-emerald-500 hover:shadow-md transition text-left flex flex-col justify-between"
                    >
                      <div className="flex justify-between items-start gap-2 w-full">
                        <div>
                          <div className="font-extrabold text-gray-900 text-base">{p.name}</div>
                          <div className="text-xs text-gray-500">{p.state}</div>
                        </div>
                        <div
                          className="px-2.5 py-1 rounded-full text-xs font-black text-white shadow-sm flex items-center gap-1 flex-shrink-0"
                          style={{ backgroundColor: aqiColor }}
                        >
                          <span>{p.aqi != null ? `AQI ${p.aqi}` : "No data"}</span>
                        </div>
                      </div>

                      <div className="mt-3 pt-2 border-t border-gray-200 w-full flex items-center justify-between text-xs text-gray-600">
                        <span className="truncate max-w-[140px]">{p.station_name || p.label || "CPCB Status"}</span>
                        <span className="text-emerald-700 font-bold">View Telemetry →</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* Loading State */}
        {loading && (
          <div className="space-y-6">
            <div className="h-96 skeleton w-full"></div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-32 skeleton"></div>
              ))}
            </div>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center my-8">
            <span className="text-3xl">⚠️</span>
            <h3 className="text-lg font-semibold text-red-900 mt-2">Data Connection Unavailable</h3>
            <p className="text-sm text-red-700 mt-1 max-w-md mx-auto">{error}</p>
            <button
              onClick={fetchData}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* 1. INTERACTIVE INDIA AQI BUBBLE MAP (Matching User Reference Image) */}
        {!loading && !error && (
          <section className="mb-10">
            <IndiaAqiMap
              places={places}
              onSelectPlace={(p) => setInspectPlace(p)}
            />
          </section>
        )}

        {/* INSPECT PLACE POPUP DRAWER (When tapping a pin on the map) */}
        {inspectPlace && (
          <section className="mb-10 bg-emerald-50/80 border-2 border-emerald-500 rounded-2xl p-6 shadow-md transition-all">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-200 text-emerald-900 uppercase">
                    Selected Location
                  </span>
                  <span className="text-xs text-gray-600 font-medium">{inspectPlace.state}</span>
                </div>
                <h3 className="text-2xl font-black text-gray-900">{inspectPlace.name}</h3>
                <div className="text-xs text-gray-700 mt-1 flex flex-wrap items-center gap-2">
                  <span>📡 Station: <strong>{inspectPlace.station_name || "Continuous Monitoring Station"}</strong></span>
                  {inspectPlace.data_age_minutes != null && (
                    <span className="text-gray-500">• ⏱️ Age: <strong>{formatDataAge(inspectPlace.data_age_minutes)}</strong></span>
                  )}
                  {inspectPlace.measurement_ts && (
                    <span className="text-gray-500">• 🕒 Measured: <strong>{new Date(inspectPlace.measurement_ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} IST</strong></span>
                  )}
                  {Boolean(inspectPlace.is_stale || (inspectPlace.data_age_minutes != null && inspectPlace.data_age_minutes > 30)) && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                      ⚠️ {formatAgeWarning(inspectPlace.data_age_minutes, inspectPlace.warning)}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4 self-center sm:self-auto">
                <div
                  className="w-20 h-20 rounded-full flex flex-col items-center justify-center text-white font-black shadow-md text-center p-1"
                  style={{ backgroundColor: inspectPlace.color || (inspectPlace.aqi != null ? "#1E9E57" : "#BDBDBD") }}
                >
                  <span className="text-2xl">{inspectPlace.aqi ?? "--"}</span>
                  <span className="text-[9px] uppercase font-bold tracking-wider leading-tight">{inspectPlace.label}</span>
                </div>

                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => navigate(`/place/${inspectPlace.id}`)}
                    className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition shadow-sm"
                  >
                    View Real-Time Station Details →
                  </button>
                  <button
                    onClick={() => setInspectPlace(null)}
                    className="px-3 py-1.5 bg-white border border-gray-300 text-gray-600 rounded-xl text-xs hover:bg-gray-50 transition"
                  >
                    Close Inspector
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* 2. REAL-TIME MONITORING STATIONS (Strictly measured, no forecast AQI) */}
        {!loading && !error && featuredStations.length > 0 && (
          <section className="mb-10 bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
              <div>
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 mb-1">
                  <span>📡 Live Ground Stations</span>
                  <span className="text-[10px] bg-emerald-200 text-emerald-900 px-1.5 py-0.2 rounded font-bold">Auto-refreshes 60s</span>
                </div>
                <h2 className="text-xl font-bold text-gray-900">
                  Featured Real-Time Monitoring Stations (Delhi, Mohali, Kharar, Chandigarh, Mumbai, etc.)
                </h2>
                <p className="text-xs text-gray-500">
                  Live sensor measurements from official ground monitoring stations (OpenAQ / WAQI / CPCB). No forecast or predicted values.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {featuredStations.map((item) => {
                const pl = item.place;
                const aqiVal = item.aqi ?? item.current_aqi;
                const isDelayed = Boolean(item.is_stale || (item.data_age_minutes != null && item.data_age_minutes > 30));
                return (
                  <div
                    key={pl.id}
                    className="border border-gray-200 rounded-xl p-4 bg-gray-50/50 hover:border-emerald-500 hover:shadow-sm transition flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <div className="font-extrabold text-gray-900 text-base">{pl.name}</div>
                          <div className="text-xs text-gray-500">{pl.state}</div>
                        </div>
                        <div
                          className="px-2.5 py-1 rounded-full text-xs font-black text-white shadow-sm"
                          style={{ backgroundColor: item.color || (aqiVal != null ? "#1E9E57" : "#BDBDBD") }}
                        >
                          {aqiVal != null ? `AQI ${aqiVal}` : "No station data"}
                        </div>
                      </div>

                      {/* Station details */}
                      <div className="mt-3 p-2.5 bg-white rounded-lg border border-gray-200 text-xs text-gray-700 space-y-1.5">
                        <div className="font-semibold text-gray-900 truncate" title={item.station_name || "Continuous Monitoring Station"}>
                          📡 {item.station_name || "Continuous Monitoring Station"}
                        </div>
                        <div className="flex items-center justify-between text-gray-600 text-[11px]">
                          <span>PM2.5: <strong>{item.pm25 != null ? `${item.pm25} μg/m³` : "--"}</strong></span>
                          <span>PM10: <strong>{item.pm10 != null ? `${item.pm10} μg/m³` : "--"}</strong></span>
                        </div>
                        <div className="flex items-center justify-between text-gray-500 text-[11px] pt-1 border-t border-gray-100">
                          <span>🕒 {item.measurement_ts ? new Date(item.measurement_ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' IST' : 'Live'}</span>
                          <span>⏱️ Age: <strong>{formatDataAge(item.data_age_minutes)}</strong></span>
                        </div>
                      </div>

                      {isDelayed && (
                        <div className="mt-2 text-[11px] font-bold text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1 flex items-center gap-1">
                          <span>⚠️</span>
                          <span>{formatAgeWarning(item.data_age_minutes, item.warning)}</span>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => navigate(`/place/${pl.id}`)}
                      className="mt-3 pt-2 border-t border-gray-200 text-xs font-semibold text-emerald-700 hover:text-emerald-800 flex items-center justify-between"
                    >
                      <span>Inspect Live Station Telemetry</span>
                      <span>→</span>
                    </button>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* 3. STATE DIRECTORY & SUBDISTRICTS GRID */}
        {!loading && !error && (
          <section className="mb-10">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-2">
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  States & Union Territories ({filteredStates.length})
                </h2>
                <p className="text-xs text-gray-500">
                  Tap any state card below to inspect all its monitored cities and subdistrict stations
                </p>
              </div>

              {selectedState && (
                <button
                  onClick={() => setSelectedState(null)}
                  className="text-xs text-emerald-700 font-medium hover:underline self-start sm:self-auto"
                >
                  ✕ Clear selected state ({selectedState})
                </button>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 sm:gap-4">
              {filteredStates.map((s) => {
                const aqiColor = s.color || "#1E9E57";
                const isSelected = selectedState === s.state;
                return (
                  <div
                    key={s.state}
                    onClick={() => {
                      if (selectedState === s.state) {
                        setSelectedState(null);
                      } else {
                        setSelectedState(s.state);
                      }
                    }}
                    className={`cursor-pointer rounded-xl p-3.5 border transition-all text-left bg-white relative flex flex-col justify-between ${
                      isSelected
                        ? "border-emerald-600 ring-2 ring-emerald-500/20 shadow-md"
                        : "border-gray-200 hover:border-emerald-400 hover:shadow-sm"
                    }`}
                  >
                    <div>
                      <div className="font-semibold text-gray-900 text-sm truncate" title={s.state}>
                        {s.state}
                      </div>
                      <div className="flex items-baseline gap-1.5 mt-1.5">
                        <span className="text-xl font-extrabold" style={{ color: aqiColor }}>
                          {s.aqi ?? "--"}
                        </span>
                        <span
                          className="px-1.5 py-0.5 rounded text-[10px] font-bold text-white uppercase tracking-wider"
                          style={{ backgroundColor: aqiColor }}
                        >
                          {s.label || "N/A"}
                        </span>
                      </div>
                    </div>

                    <div className="mt-2 text-[11px] text-gray-600">
                      <span>{s.n_places_with_data} places</span>
                      {s.n_ground > 0 && (
                        <span className="ml-1 text-emerald-800 font-medium">({s.n_ground} ground)</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* SELECTED STATE SUBDISTRICTS DRAWER */}
        {!loading && !error && selectedState && (
          <section className="bg-emerald-50/60 border border-emerald-200 rounded-2xl p-6 mb-10">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900">
                  Monitored Places & Stations in {selectedState}
                </h3>
                <p className="text-xs text-gray-600">
                  Select a city to inspect readings, ground sensor attribution, and 5-day AI forecast
                </p>
              </div>
              <button
                onClick={() => setSelectedState(null)}
                className="text-xs bg-white px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:text-gray-900 shadow-sm"
              >
                Close
              </button>
            </div>

            {placesInSelectedState.length === 0 ? (
              <p className="text-sm text-gray-500 italic">No specific cities recorded for this state yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {placesInSelectedState.map((p) => {
                  const aqiColor = p.color || "#1E9E57";
                  return (
                    <button
                      key={p.id}
                      onClick={() => navigate(`/place/${p.id}`)}
                      className="bg-white p-4 rounded-xl border border-gray-200 hover:border-emerald-500 hover:shadow-md transition text-left flex items-center justify-between"
                    >
                      <div>
                        <div className="font-semibold text-gray-900 text-sm">{p.name}</div>
                        <div className="text-xs text-gray-500">
                          {p.has_ground_station ? "📡 Ground Station" : "🛰️ Atmospheric Grid"}
                        </div>
                      </div>

                      <div
                        className="px-2.5 py-1 rounded-full text-xs font-bold text-white shadow-sm"
                        style={{ backgroundColor: aqiColor }}
                      >
                        {p.aqi ?? "--"}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* 5. CPCB SCALE REFERENCE TABLE */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900 mb-2">
            Central Pollution Control Board (CPCB) AQI Categories
          </h2>
          <p className="text-xs text-gray-500 mb-6">
            Official Indian standard breakpoints calculated over 24-hour PM2.5 and PM10 concentrations (μg/m³).
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
            {CPCB_SCALE.map((band) => (
              <div
                key={band.label}
                className="rounded-xl p-3.5 border border-gray-100 flex flex-col justify-between"
                style={{ backgroundColor: `${band.color}15` }}
              >
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: band.color }}
                    ></span>
                    <span className="font-bold text-xs text-gray-900">{band.label}</span>
                  </div>
                  <div className="text-xs font-semibold text-gray-700">{band.range}</div>
                </div>
                <div className="mt-2 text-[11px] text-gray-600 leading-snug">{band.desc}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 pt-4 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500">
            <div>
              <span>Learn how high AQI affects vulnerable health groups: </span>
              <Link to="/about" className="text-emerald-700 font-semibold hover:underline">
                Read About & Health Guide →
              </Link>
            </div>
            <div>
              Data sources: <span className="font-medium text-gray-700">CPCB / OpenAQ v3</span> & <span className="font-medium text-gray-700">Open-Meteo</span>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-white border-t border-gray-200 py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-gray-500 gap-4">
          <div className="flex items-center gap-2">
            <span>🌿 AirSense India</span>
            <span>•</span>
            <span>Non-commercial open environmental analytics</span>
          </div>
          <div>
            Built strictly in accordance with Indian Standard Time (IST) & CPCB 2014 standards.
          </div>
        </div>
      </footer>

      {/* Floating Ask AirSense AI Assistant with 10-query limit */}
      <AiAssistantModal />
    </div>
  );
}
