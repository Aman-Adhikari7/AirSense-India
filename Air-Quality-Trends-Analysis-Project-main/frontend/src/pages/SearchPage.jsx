import React, { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import AiAssistantModal from "../components/AiAssistantModal";

const API = import.meta.env.VITE_API_BASE ?? "";

const CATEGORIES = [
  { label: "All Categories", value: "all" },
  { label: "Good (0-50)", value: "good", color: "#1E9E57" },
  { label: "Satisfactory (51-100)", value: "satisfactory", color: "#8BC34A" },
  { label: "Moderate (101-200)", value: "moderate", color: "#F4C20D" },
  { label: "Poor (201-300)", value: "poor", color: "#F28C28" },
  { label: "Very Poor (301-400)", value: "very_poor", color: "#D32F2F" },
  { label: "Severe (401-500)", value: "severe", color: "#7B1113" },
];

export default function SearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [places, setPlaces] = useState([]);
  const [states, setStates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [query, setQuery] = useState(initialQuery);
  const [selectedState, setSelectedState] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [stateSort, setStateSort] = useState("aqi_desc"); // 'aqi_desc' | 'aqi_asc' | 'alpha'
  const [stationSort, setStationSort] = useState("name_asc");

  const stationsSectionRef = useRef(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    axios
      .get(`${API}/map/summary`)
      .then((res) => {
        if (!isMounted) return;
        setPlaces(res.data.places || []);
        setStates(res.data.states || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("Search fetch error:", err);
        setError("Unable to load stations catalogue. Please ensure the backend is running.");
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Sync URL search params
  const handleQueryChange = (val) => {
    setQuery(val);
    if (val.trim()) {
      setSearchParams({ q: val.trim() });
    } else {
      setSearchParams({});
    }
  };

  const handleStateClick = (stateName) => {
    if (selectedState === stateName) {
      setSelectedState("all");
    } else {
      setSelectedState(stateName);
      // Smooth scroll down to stations list
      setTimeout(() => {
        stationsSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  };

  // Sort States for the Bar Graph
  const sortedStates = [...states].sort((a, b) => {
    if (stateSort === "aqi_desc") {
      return (b.aqi ?? -1) - (a.aqi ?? -1);
    }
    if (stateSort === "aqi_asc") {
      return (a.aqi ?? 9999) - (b.aqi ?? 9999);
    }
    return a.state.localeCompare(b.state);
  });

  // Filter places
  const filtered = places.filter((p) => {
    const q = query.toLowerCase().trim();
    const matchQuery =
      !q ||
      p.name.toLowerCase().includes(q) ||
      (p.state && p.state.toLowerCase().includes(q)) ||
      (p.station_name && p.station_name.toLowerCase().includes(q));

    const matchState =
      selectedState === "all" ||
      (p.state && p.state.toLowerCase() === selectedState.toLowerCase());

    const matchCat =
      selectedCategory === "all" ||
      (p.key && p.key.toLowerCase() === selectedCategory.toLowerCase());

    return matchQuery && matchState && matchCat;
  });

  // Sort stations
  const sortedStations = [...filtered].sort((a, b) => {
    if (stationSort === "name_asc") {
      return a.name.localeCompare(b.name);
    }
    if (stationSort === "aqi_desc") {
      return (b.aqi ?? -1) - (a.aqi ?? -1);
    }
    if (stationSort === "aqi_asc") {
      return (a.aqi ?? 9999) - (b.aqi ?? 9999);
    }
    return 0;
  });

  // Max AQI for visual scaling
  const maxStateAqi = Math.max(...states.map((s) => s.aqi || 0), 250);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Page Title & Intro */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 shadow-sm">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 mb-3">
              <span>📊 Visual Environmental Analytics</span>
            </div>
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
              State Air Quality Ranking & Station Directory
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              Interactive visual bar chart comparing average CPCB Air Quality Index across all 36 Indian States and Union Territories.
              Click any state bar to filter the active monitoring stations.
            </p>
          </div>
        </section>

        {/* VISUAL BAR GRAPH OF EVERY STATE */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-gray-100">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl">📊</span>
                <h2 className="text-lg font-bold text-gray-900">
                  State-by-State AQI Level Bar Graph ({states.length} States & UTs)
                </h2>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Bars represent average 24h particulate AQI. Colors reflect official CPCB air health bands.
              </p>
            </div>

            {/* Sort Options for Bar Graph */}
            <div className="flex items-center gap-2 text-xs">
              <span className="font-semibold text-gray-600">Sort by:</span>
              <div className="inline-flex rounded-lg border border-gray-200 p-1 bg-gray-50">
                <button
                  onClick={() => setStateSort("aqi_desc")}
                  className={`px-2.5 py-1 rounded-md font-medium transition ${
                    stateSort === "aqi_desc"
                      ? "bg-white text-emerald-800 shadow-xs font-bold"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  Most Polluted First
                </button>
                <button
                  onClick={() => setStateSort("aqi_asc")}
                  className={`px-2.5 py-1 rounded-md font-medium transition ${
                    stateSort === "aqi_asc"
                      ? "bg-white text-emerald-800 shadow-xs font-bold"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  Cleanest First
                </button>
                <button
                  onClick={() => setStateSort("alpha")}
                  className={`px-2.5 py-1 rounded-md font-medium transition ${
                    stateSort === "alpha"
                      ? "bg-white text-emerald-800 shadow-xs font-bold"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  A → Z
                </button>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="space-y-3 pt-6">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="h-10 skeleton rounded-lg"></div>
              ))}
            </div>
          ) : (
            <div className="pt-6 grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-3">
              {sortedStates.map((s) => {
                const aqiVal = s.aqi;
                const aqiColor = s.color || (aqiVal != null ? "#1E9E57" : "#BDBDBD");
                const barWidth = aqiVal ? Math.min(100, Math.max(12, (aqiVal / maxStateAqi) * 100)) : 8;
                const isSelected = selectedState.toLowerCase() === s.state.toLowerCase();

                return (
                  <div
                    key={s.state}
                    onClick={() => handleStateClick(s.state)}
                    className={`group cursor-pointer rounded-xl p-2.5 transition-all border ${
                      isSelected
                        ? "bg-emerald-50/80 border-emerald-600 ring-2 ring-emerald-500/20 shadow-sm"
                        : "bg-gray-50/50 hover:bg-white border-gray-200 hover:border-emerald-400 hover:shadow-xs"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-gray-900 group-hover:text-emerald-700 transition">
                          {s.state}
                        </span>
                        <span className="text-[10px] text-gray-600 font-medium">
                          ({s.n_places_with_data} {s.n_places_with_data === 1 ? "place" : "places"})
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className="px-2 py-0.5 rounded text-[10px] font-bold text-white uppercase tracking-wider"
                          style={{ backgroundColor: aqiColor }}
                        >
                          {s.label || "N/A"}
                        </span>
                        <span className="font-extrabold text-sm w-9 text-right" style={{ color: aqiColor }}>
                          {aqiVal ?? "--"}
                        </span>
                      </div>
                    </div>

                    {/* Visual Bar Indicator */}
                    <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden flex">
                      <div
                        className="h-full rounded-full transition-all duration-500 ease-out"
                        style={{
                          width: `${barWidth}%`,
                          backgroundColor: aqiColor,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {selectedState !== "all" && (
            <div className="mt-6 pt-4 border-t border-gray-100 flex items-center justify-between">
              <div className="text-xs text-gray-700 flex items-center gap-2">
                <span className="font-bold">Active Filter:</span>
                <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-900 font-bold text-xs">
                  {selectedState}
                </span>
              </div>
              <button
                onClick={() => setSelectedState("all")}
                className="text-xs text-emerald-700 font-bold hover:underline"
              >
                ✕ Clear State Filter (Show All India)
              </button>
            </div>
          )}
        </section>

        {/* CITY & MONITORING STATION EXPLORER */}
        <section ref={stationsSectionRef} className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                <span>City Monitoring Stations</span>
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-700">
                  {sortedStations.length} found
                </span>
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                {selectedState !== "all"
                  ? `Displaying monitoring stations located in ${selectedState}`
                  : "Search any Indian city, subdistrict, or official continuous monitoring station"}
              </p>
            </div>

            {/* Quick Sort for Station Cards */}
            <div className="flex items-center gap-2 text-xs">
              <span className="font-semibold text-gray-600">Sort stations:</span>
              <select
                value={stationSort}
                onChange={(e) => setStationSort(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-xs font-medium text-gray-800 focus:ring-2 focus:ring-emerald-500"
              >
                <option value="name_asc">City Name (A → Z)</option>
                <option value="aqi_desc">AQI (Highest First)</option>
                <option value="aqi_asc">AQI (Lowest First)</option>
              </select>
            </div>
          </div>

          {/* Search Bar & Category Filters */}
          <div className="space-y-4 mb-6">
            <div className="relative">
              <input
                type="text"
                placeholder="Search city, state, or monitoring station (e.g. Chandigarh, Mohali, Kharar, Delhi, Mumbai)..."
                value={query}
                onChange={(e) => handleQueryChange(e.target.value)}
                className="w-full px-4 py-3 pl-11 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 bg-white text-gray-900 placeholder-gray-400 text-sm shadow-xs"
              />
              <span className="absolute left-4 top-3.5 text-gray-400 text-lg">🔍</span>
              {query && (
                <button
                  onClick={() => handleQueryChange("")}
                  className="absolute right-3 top-3 text-xs text-gray-500 hover:text-gray-800 bg-gray-100 px-2.5 py-1 rounded-md"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
              <span className="text-gray-600 font-semibold mr-1">Category:</span>
              {CATEGORIES.map((c) => {
                const isSelected = selectedCategory === c.value;
                return (
                  <button
                    key={c.value}
                    onClick={() => setSelectedCategory(c.value)}
                    className={`whitespace-nowrap px-3 py-1 rounded-full font-medium transition ${
                      isSelected
                        ? "bg-emerald-700 text-white font-bold shadow-xs"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Station Cards Grid */}
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-44 skeleton rounded-xl"></div>
              ))}
            </div>
          ) : sortedStations.length === 0 ? (
            <div className="bg-gray-50 rounded-xl border border-gray-200 p-8 text-center my-4">
              <span className="text-3xl">🔍</span>
              <h3 className="text-base font-bold text-gray-900 mt-2">No Matching Stations Found</h3>
              <p className="text-xs text-gray-500 mt-1 max-w-md mx-auto">
                No stations match your current filters. Try resetting the state filter or search query.
              </p>
              <button
                onClick={() => {
                  handleQueryChange("");
                  setSelectedState("all");
                  setSelectedCategory("all");
                }}
                className="mt-3 px-4 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 transition"
              >
                Reset All Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {sortedStations.map((p) => {
                const aqiVal = p.aqi;
                const aqiColor = p.color || (aqiVal != null ? "#1E9E57" : "#BDBDBD");
                const isDelayed = Boolean(p.is_stale || (p.data_age_minutes != null && p.data_age_minutes > 30));

                return (
                  <div
                    key={p.id}
                    className="bg-white rounded-xl border border-gray-200 p-4 hover:border-emerald-500 hover:shadow-md transition flex flex-col justify-between"
                  >
                    <div>
                      {/* City & AQI Badge */}
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="font-extrabold text-gray-900 text-base leading-tight">{p.name}</h3>
                          <p className="text-xs text-gray-500">{p.state}</p>
                        </div>
                        <div
                          className="px-2.5 py-1 rounded-full text-xs font-black text-white shadow-xs flex items-center gap-1 flex-shrink-0"
                          style={{ backgroundColor: aqiColor }}
                        >
                          <span>{aqiVal != null ? `AQI ${aqiVal}` : "No station data"}</span>
                        </div>
                      </div>

                      {/* Station details */}
                      <div className="mt-3 p-2.5 bg-gray-50 rounded-lg border border-gray-100 text-xs text-gray-700 space-y-1">
                        <div className="font-semibold text-gray-900 truncate" title={p.station_name || "Continuous Ambient Air Station"}>
                          📡 {p.station_name || "Continuous Monitoring Station"}
                        </div>
                        <div className="flex items-center justify-between text-gray-600 text-[11px]">
                          <span>Status: <strong>{p.label || "CPCB Status"}</strong></span>
                          <span>{p.source || "Ground Station"}</span>
                        </div>
                        {p.data_age_minutes != null && (
                          <div className="text-[11px] text-gray-500 pt-1 border-t border-gray-200 flex justify-between">
                            <span>⏱️ Updated: {p.data_age_minutes}m ago</span>
                            {isDelayed && (
                              <span className="text-amber-800 font-bold">⚠️ &gt;30m delay</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Navigation Link */}
                    <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
                      <span className="text-xs text-gray-600 font-medium">
                        {p.kind ? p.kind.replace("_", " ") : "city"}
                      </span>
                      <Link
                        to={`/place/${p.id}`}
                        className="px-3 py-1.5 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 rounded-lg text-xs font-bold transition flex items-center gap-1"
                      >
                        <span>Live Telemetry & Forecast</span>
                        <span>→</span>
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </main>

      {/* Floating AI Assistant */}
      <AiAssistantModal />
    </div>
  );
}
