import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import AiAssistantModal from "../components/AiAssistantModal";
import ForecastChart from "../components/ForecastChart";

const API = import.meta.env.VITE_API_BASE ?? "";

export default function PlacePage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [live, setLive] = useState(null);
  const [forecast5d, setForecast5d] = useState(null);
  const [forecast30d, setForecast30d] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selected5dIndex, setSelected5dIndex] = useState(0);
  const [seasonalViewMode, setSeasonalViewMode] = useState("chart"); // 'chart' | 'table'
  const [selected30dIndex, setSelected30dIndex] = useState(0);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    const loadData = async () => {
      try {
        // Fetch Live AQI
        const liveRes = await axios.get(`${API}/places/${id}/live`);
        if (isMounted) setLive(liveRes.data);

        // Fetch 5-Day Festival ML Forecast
        try {
          const fc5Res = await axios.get(`${API}/places/${id}/forecast?model=festival-gbm`);
          if (isMounted) setForecast5d(fc5Res.data);
        } catch (fcErr) {
          console.warn("5-day forecast not yet computed:", fcErr?.response?.status);
        }

        // Fetch 6-30 Day Seasonal Outlook
        try {
          const fc30Res = await axios.get(`${API}/places/${id}/forecast?model=seasonal-outlook`);
          if (isMounted) setForecast30d(fc30Res.data);
        } catch (sErr) {
          console.warn("Seasonal outlook not available:", sErr?.response?.status);
        }
      } catch (err) {
        console.error("Failed to load place live data:", err);
        if (isMounted) setError("Could not load details for this place. Please try again.");
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadData();
    return () => {
      isMounted = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Header />
        <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8 space-y-6">
          <div className="h-6 w-36 skeleton"></div>
          <div className="h-64 skeleton rounded-2xl"></div>
          <div className="h-96 skeleton rounded-2xl"></div>
        </main>
      </div>
    );
  }

  if (error || !live) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Header />
        <main className="flex-1 max-w-xl mx-auto px-4 py-16 text-center">
          <span className="text-4xl">⚠️</span>
          <h2 className="text-xl font-bold text-gray-900 mt-3">{error || "Place Not Found"}</h2>
          <p className="text-sm text-gray-600 mt-1">Unable to locate live monitoring data for ID {id}.</p>
          <button
            onClick={() => navigate("/")}
            className="mt-6 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition"
          >
            ← Return to India Map
          </button>
        </main>
      </div>
    );
  }

  const place = live.place || {};
  const aqiObj = live.aqi;
  const aqiVal = aqiObj ? aqiObj.aqi : null;
  const aqiColor = aqiObj ? aqiObj.color : "#BDBDBD";
  const aqiLabel = aqiObj ? aqiObj.label : (live.aqi_reason || "No 24h Data");
  const latest = live.latest || {};

  // 5-Day Trend Calculation
  const days5 = forecast5d?.days || [];
  const firstDayAqi = days5[0]?.aqi;
  const lastDayAqi = days5[days5.length - 1]?.aqi;
  const aqiDelta = firstDayAqi !== undefined && lastDayAqi !== undefined ? lastDayAqi - firstDayAqi : 0;

  // 30-Day Highlights
  const days30 = forecast30d?.days || [];
  const peakDay = days30.length > 0 ? [...days30].sort((a, b) => (b.aqi || 0) - (a.aqi || 0))[0] : null;
  const cleanestDay = days30.length > 0 ? [...days30].sort((a, b) => (a.aqi || 0) - (b.aqi || 0))[0] : null;
  const avg30Aqi = days30.length > 0 ? Math.round(days30.reduce((acc, d) => acc + (d.aqi || 0), 0) / days30.length) : null;

  // Safe percentage helper for NAAQS gauges (PM2.5 limit = 60, PM10 limit = 100)
  const pm25Pct = latest.pm25 ? Math.min(100, Math.round((latest.pm25 / 60) * 100)) : 0;
  const pm10Pct = latest.pm10 ? Math.min(100, Math.round((latest.pm10 / 100) * 100)) : 0;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate("/")}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700 hover:text-emerald-800 transition"
          >
            <span>← Back to National Map</span>
          </button>

          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>Live CPCB Telemetry • {place.lat?.toFixed(2)}°N, {place.lon?.toFixed(2)}°E</span>
          </div>
        </div>

        {/* 🌟 HERO: LIVE GROUND TELEMETRY BANNER */}
        <section className="bg-white rounded-3xl border border-gray-200 p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 uppercase tracking-wider">
                  {place.kind || "City"}
                </span>
                <span className="text-xs font-semibold text-gray-500">{place.state}</span>
                <span className="text-gray-300">•</span>
                <span className="text-xs text-gray-500 font-medium">District: {place.district || place.name}</span>
              </div>

              <h1 className="text-3xl sm:text-5xl font-black text-gray-900 tracking-tight">
                {place.name}
              </h1>

              {/* Station Telemetry Source Badge */}
              <div className="mt-3.5 inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-700">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
                </span>
                <span className="font-semibold text-gray-900">
                  {place.has_ground_station ? "📡 CAAQMS Ground Sensor:" : "🛰️ Atmospheric Feed:"}
                </span>
                <span className="text-gray-600 truncate max-w-xs">{live.source}</span>
              </div>

              {latest.stale && (
                <div className="mt-2 text-xs text-amber-700 font-semibold flex items-center gap-1.5">
                  <span>⚠️</span>
                  <span>Reading delayed &gt; 30 min (feed flagged as stale)</span>
                </div>
              )}

              {/* Comparative NAAQS Progress Bars */}
              <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg">
                <div className="bg-gray-50/80 p-3 rounded-xl border border-gray-200/80">
                  <div className="flex justify-between items-center text-xs mb-1">
                    <span className="font-semibold text-gray-700">PM2.5: {latest.pm25 ? `${latest.pm25.toFixed(1)} μg/m³` : "N/A"}</span>
                    <span className={`text-[10px] font-bold ${pm25Pct > 100 ? "text-red-600" : "text-emerald-700"}`}>
                      {pm25Pct}% of NAAQS (60 μg/m³)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${pm25Pct > 100 ? "bg-red-500" : "bg-emerald-500"}`}
                      style={{ width: `${Math.min(100, pm25Pct)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="bg-gray-50/80 p-3 rounded-xl border border-gray-200/80">
                  <div className="flex justify-between items-center text-xs mb-1">
                    <span className="font-semibold text-gray-700">PM10: {latest.pm10 ? `${latest.pm10.toFixed(1)} μg/m³` : "N/A"}</span>
                    <span className={`text-[10px] font-bold ${pm10Pct > 100 ? "text-red-600" : "text-emerald-700"}`}>
                      {pm10Pct}% of NAAQS (100 μg/m³)
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${pm10Pct > 100 ? "bg-red-500" : "bg-emerald-500"}`}
                      style={{ width: `${Math.min(100, pm10Pct)}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Glowing Hero Radial Dial */}
            <div className="self-center lg:self-auto flex flex-col items-center">
              <div
                className="w-36 h-36 sm:w-44 sm:h-44 rounded-full flex flex-col items-center justify-center border-6 text-center bg-white transition-transform hover:scale-105 duration-300"
                style={{
                  borderColor: aqiColor,
                  boxShadow: `0 12px 30px -8px ${aqiColor}55`,
                }}
              >
                <span className="text-xs uppercase font-extrabold tracking-widest text-gray-400">Current AQI</span>
                <span className="text-5xl sm:text-6xl font-black tracking-tight" style={{ color: aqiColor }}>
                  {aqiVal ?? "--"}
                </span>
                <span
                  className="mt-1 px-3 py-0.5 rounded-full text-[11px] font-extrabold text-white uppercase tracking-wider shadow-xs"
                  style={{ backgroundColor: aqiColor }}
                >
                  {aqiLabel}
                </span>
              </div>

              <span className="text-[11px] text-gray-400 mt-2 font-medium">
                Updated: {latest.ts ? new Date(latest.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Live"} IST
              </span>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-100 flex flex-wrap items-center justify-between text-xs text-gray-500 gap-2">
            <span>24h Telemetry Validity: {live.hours_24h} of 24 hours recorded</span>
            <span>Ground Station Telemetry Ratio: {((live.ground_share_24h || 0) * 100).toFixed(0)}%</span>
            <span>Governing Metric: {aqiObj?.dominant ? aqiObj.dominant.toUpperCase() : "PM2.5"} Maximum Breakpoint</span>
          </div>
        </section>

        {/* 🤖 5-DAY FESTIVAL-AWARE AI FORECAST (GRAPHICAL PREDICTION CENTER) */}
        <section className="bg-white rounded-3xl border border-gray-200 p-6 sm:p-8 shadow-sm space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 mb-2">
                <span>🤖 Festival-Aware HistGradientBoosting Model</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
                5-Day AI Air Quality Forecast
              </h2>
            </div>

            {/* Trajectory Direction Indicator */}
            {days5.length > 0 && (
              <div className="flex items-center gap-2">
                {aqiDelta > 10 ? (
                  <span className="px-3 py-1.5 rounded-xl text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200 flex items-center gap-1.5">
                    <span>📈 Projected Surge:</span>
                    <span>+{aqiDelta} AQI</span>
                  </span>
                ) : aqiDelta < -10 ? (
                  <span className="px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
                    <span>📉 Projected Clearance:</span>
                    <span>{aqiDelta} AQI</span>
                  </span>
                ) : (
                  <span className="px-3 py-1.5 rounded-xl text-xs font-bold bg-blue-50 text-blue-800 border border-blue-200 flex items-center gap-1.5">
                    <span>➡️ Steady Conditions:</span>
                    <span>±{Math.abs(aqiDelta)} AQI</span>
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Upcoming Festival Surge Warning */}
          {forecast5d?.upcoming_festivals?.length > 0 && (
            <div className="p-4 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl text-xs text-amber-950 flex items-start gap-3">
              <span className="text-xl leading-none">🎆</span>
              <div>
                <span className="font-extrabold">Active Festival Surge Trigger: </span>
                {forecast5d.upcoming_festivals.map((f, i) => (
                  <span key={f.festival} className="font-semibold">
                    {f.festival.toUpperCase()} in {f.in_days} days ({f.date})
                    {i < forecast5d.upcoming_festivals.length - 1 ? ", " : ""}
                  </span>
                ))}
                <span className="block mt-0.5 text-amber-900/90">
                  The model dynamically applies non-linear combustion surge multipliers to account for anticipated celebratory firecracker spikes.
                </span>
              </div>
            </div>
          )}

          {/* 📈 INTERACTIVE SVG FORECAST CHART */}
          {days5.length > 0 && (
            <ForecastChart
              days={days5}
              activeIndex={selected5dIndex}
              onSelectDay={(idx) => setSelected5dIndex(idx)}
            />
          )}

          {/* 🗂️ 5-DAY GRAPHICAL CARD TILES */}
          {days5.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3.5">
              {days5.map((d, idx) => {
                const dayDate = new Date(d.date);
                const weekday = dayDate.toLocaleDateString("en-IN", { weekday: "short" });
                const monthDay = dayDate.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
                const cardColor = d.color || "#059669";
                const isSelected = idx === selected5dIndex;
                const meterPct = Math.min(100, Math.round(((d.aqi || 0) / 400) * 100));

                return (
                  <div
                    key={d.date}
                    onClick={() => setSelected5dIndex(idx)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between text-center relative overflow-hidden ${
                      isSelected
                        ? "bg-white border-emerald-500 shadow-md ring-2 ring-emerald-500/30 scale-[1.02]"
                        : "bg-white border-gray-200/90 hover:border-gray-300 hover:shadow-xs"
                    }`}
                  >
                    {/* Top Color Accent Strip */}
                    <div className="absolute top-0 left-0 right-0 h-1.5" style={{ backgroundColor: cardColor }}></div>

                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-extrabold text-gray-900">{weekday}</span>
                        <span className="text-[11px] text-gray-500 font-medium">{monthDay}</span>
                      </div>

                      {/* Big AQI Number with Subtle Glow */}
                      <div className="my-2.5">
                        <span className="text-3xl sm:text-4xl font-black tracking-tight" style={{ color: cardColor }}>
                          {d.aqi ?? "--"}
                        </span>
                      </div>

                      {/* Category Badge */}
                      <span
                        className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold text-white uppercase tracking-wider inline-block shadow-2xs"
                        style={{ backgroundColor: cardColor }}
                      >
                        {d.label}
                      </span>

                      {/* Mini Metric Gauge Bar */}
                      <div className="w-full bg-gray-100 h-1.5 rounded-full mt-3 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{ width: `${meterPct}%`, backgroundColor: cardColor }}
                        ></div>
                      </div>
                    </div>

                    <div className="mt-3 pt-2.5 border-t border-gray-100 text-[11px] space-y-1 text-gray-600">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-400">PM2.5:</span>
                        <span className="font-bold text-gray-800">{d.pm25} μg/m³</span>
                      </div>
                      <div className="flex justify-between items-center text-[10px] text-gray-400">
                        <span>80% Range:</span>
                        <span className="font-semibold text-gray-600">
                          {d.aqi_low ?? "?"} – {d.aqi_high ?? "?"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 bg-gray-50 border border-gray-200 rounded-2xl text-center text-sm text-gray-500">
              5-day forecast points are being dynamically calculated...
            </div>
          )}

          {/* 🧠 AI FEATURE ATTRIBUTION & DIAGNOSTICS */}
          <div className="bg-gray-50/80 rounded-2xl p-4 sm:p-5 border border-gray-200/80">
            <h4 className="text-xs font-extrabold text-gray-700 uppercase tracking-wider mb-3">
              Predictive Feature Weighting (HistGradientBoosting Architecture)
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-white rounded-xl border border-gray-200">
                <div className="flex items-center gap-1.5 font-bold text-gray-900 mb-0.5">
                  <span>🎆</span>
                  <span>Festival Multiplier</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-tight">
                  Calculates signed day-distance to Diwali, Dussehra & Holi to predict non-linear firecracker spikes.
                </p>
              </div>

              <div className="p-3 bg-white rounded-xl border border-gray-200">
                <div className="flex items-center gap-1.5 font-bold text-gray-900 mb-0.5">
                  <span>🌾</span>
                  <span>Stubble Residue Index</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-tight">
                  Tracks active post-harvest burning flags in Punjab/Haryana with wind trajectory modeling.
                </p>
              </div>

              <div className="p-3 bg-white rounded-xl border border-gray-200">
                <div className="flex items-center gap-1.5 font-bold text-gray-900 mb-0.5">
                  <span>❄️</span>
                  <span>Thermal Inversion</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-tight">
                  Harmonic sinusoidal Day-of-Year [sin(DOY), cos(DOY)] capturing planetary boundary layer drops.
                </p>
              </div>

              <div className="p-3 bg-white rounded-xl border border-gray-200">
                <div className="flex items-center gap-1.5 font-bold text-gray-900 mb-0.5">
                  <span>⏱️</span>
                  <span>48h Sensor Lags</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-tight">
                  Lag-0, 3-day, 7-day autoregressive moving averages computed from CAAQMS telemetry.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 📅 EXTENDED SEASONAL OUTLOOK (DAYS 6 TO 30) */}
        {days30.length > 0 && (
          <section className="bg-white rounded-3xl border border-gray-200 p-6 sm:p-8 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-800 border border-blue-200 mb-2">
                  <span>📅 Days 6 - 30 Situational Outlook</span>
                </div>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
                  Extended Seasonal Baseline
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Based on historical circular Day-of-Year baselines (DOY ± 15 days) and 25th-75th Interquartile Range (IQR).
                </p>
              </div>

              {/* View Mode Toggle Button */}
              <div className="flex items-center bg-gray-100 p-1 rounded-xl self-start sm:self-auto text-xs font-semibold">
                <button
                  onClick={() => setSeasonalViewMode("chart")}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    seasonalViewMode === "chart"
                      ? "bg-white text-gray-900 shadow-xs font-bold"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  📊 Graphical Trend
                </button>
                <button
                  onClick={() => setSeasonalViewMode("table")}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    seasonalViewMode === "table"
                      ? "bg-white text-gray-900 shadow-xs font-bold"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  📋 Data Table
                </button>
              </div>
            </div>

            {/* Quick Summary Highlights */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200 flex items-center justify-between">
                <div>
                  <span className="text-gray-400 block font-medium">Projected Peak AQI</span>
                  <span className="text-lg font-black" style={{ color: peakDay?.color || "#D32F2F" }}>
                    AQI {peakDay?.aqi ?? "--"}
                  </span>
                </div>
                <span className="text-[11px] font-semibold text-gray-500">{peakDay?.date}</span>
              </div>

              <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200 flex items-center justify-between">
                <div>
                  <span className="text-gray-400 block font-medium">Projected Cleanest Window</span>
                  <span className="text-lg font-black" style={{ color: cleanestDay?.color || "#1E9E57" }}>
                    AQI {cleanestDay?.aqi ?? "--"}
                  </span>
                </div>
                <span className="text-[11px] font-semibold text-gray-500">{cleanestDay?.date}</span>
              </div>

              <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200 flex items-center justify-between">
                <div>
                  <span className="text-gray-400 block font-medium">Seasonal Median Baseline</span>
                  <span className="text-lg font-black text-gray-800">
                    AQI {avg30Aqi ?? "--"}
                  </span>
                </div>
                <span className="text-[11px] font-semibold text-gray-500">25-Day Average</span>
              </div>
            </div>

            {/* View Mode Content */}
            {seasonalViewMode === "chart" ? (
              <ForecastChart
                days={days30}
                activeIndex={selected30dIndex}
                onSelectDay={(idx) => setSelected30dIndex(idx)}
              />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200">
                <table className="min-w-full text-left text-xs">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 text-gray-600 font-bold uppercase tracking-wider text-[11px]">
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4">Expected PM2.5</th>
                      <th className="py-3 px-4">Expected AQI</th>
                      <th className="py-3 px-4">Historical Range (25th - 75th %)</th>
                      <th className="py-3 px-4">CPCB Band</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {days30.map((r) => {
                      const rowColor = r.color || "#059669";
                      return (
                        <tr key={r.date} className="hover:bg-gray-50/80 transition">
                          <td className="py-2.5 px-4 font-semibold text-gray-900">{r.date}</td>
                          <td className="py-2.5 px-4 text-gray-700 font-medium">{r.pm25} μg/m³</td>
                          <td className="py-2.5 px-4 font-black" style={{ color: rowColor }}>
                            {r.aqi ?? "--"}
                          </td>
                          <td className="py-2.5 px-4 text-gray-500">
                            AQI {r.aqi_low ?? "?"} – {r.aqi_high ?? "?"}
                          </td>
                          <td className="py-2.5 px-4">
                            <span
                              className="px-2.5 py-0.5 rounded-full text-[10px] font-bold text-white uppercase shadow-2xs"
                              style={{ backgroundColor: rowColor }}
                            >
                              {r.label}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* 🩺 ACTIONABLE CPCB HEALTH GUIDELINES */}
        <section className="bg-gradient-to-br from-emerald-50/80 via-white to-emerald-50/50 border border-emerald-200/80 rounded-3xl p-6 sm:p-8 shadow-sm">
          <div className="flex items-start gap-4">
            <span className="text-4xl p-2 bg-emerald-100 rounded-2xl">🩺</span>
            <div className="space-y-2">
              <h3 className="text-xl font-bold text-gray-900">
                Actionable Health Precautions for Current AQI ({aqiLabel})
              </h3>
              <p className="text-sm text-gray-700 leading-relaxed">
                {aqiVal <= 100 ? (
                  "Air quality is clean and acceptable. Outdoor exercise, jogging, and children's sports activities are completely safe."
                ) : aqiVal <= 200 ? (
                  "Moderate particulate pollution. Asthmatics, individuals with COPD, the elderly, and young children should reduce intense prolonged outdoor exertion."
                ) : aqiVal <= 300 ? (
                  "Poor air quality warning: Prolonged outdoor exposure can cause respiratory discomfort and coughing. Wearing a certified N95 respirator is strongly advised."
                ) : (
                  "Very Poor to Severe pollution hazard: Everyone is at risk of noticeable cardiovascular and respiratory distress. Keep windows sealed, avoid outdoor cardio, and run indoor HEPA air purifiers."
                )}
              </p>

              <div className="pt-2">
                <Link to="/about" className="text-xs font-bold text-emerald-800 hover:text-emerald-900 underline inline-flex items-center gap-1">
                  <span>Explore complete CPCB medical thresholds & WHO comparisons</span>
                  <span>→</span>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <AiAssistantModal placeId={place.id} placeName={place.name} />
    </div>
  );
}
