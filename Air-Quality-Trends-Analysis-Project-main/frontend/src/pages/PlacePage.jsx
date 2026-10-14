import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import AiAssistantModal from "../components/AiAssistantModal";

const API = import.meta.env.VITE_API_BASE ?? "";

export default function PlacePage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [live, setLive] = useState(null);
  const [forecast5d, setForecast5d] = useState(null);
  const [forecast30d, setForecast30d] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
        <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8 space-y-6">
          <div className="h-6 w-32 skeleton"></div>
          <div className="h-64 skeleton"></div>
          <div className="h-48 skeleton"></div>
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

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Navigation Breadcrumb */}
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={() => navigate("/")}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:text-emerald-800 transition"
          >
            <span>← Back to India Overview</span>
          </button>

          <span className="text-xs text-gray-500">
            Coordinates: {place.lat?.toFixed(2)}°N, {place.lon?.toFixed(2)}°E
          </span>
        </div>

        {/* Place Header & Live AQI Banner */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 mb-8 shadow-sm">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-gray-100 text-gray-700 uppercase">
                  {place.kind || "City"}
                </span>
                <span className="text-xs text-gray-600 font-medium">{place.state}</span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">
                {place.name}
              </h1>

              {/* Attribution Source Badge */}
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-700">
                <span>{place.has_ground_station ? "📡" : "🛰️"}</span>
                <span className="font-medium">{live.source}</span>
              </div>

              {latest.stale && (
                <div className="mt-2 text-xs text-amber-700 font-medium flex items-center gap-1">
                  <span>⚠️</span>
                  <span>Latest reading is older than 3 hours (flagged stale)</span>
                </div>
              )}
            </div>

            {/* Prominent AQI Dial */}
            <div className="flex items-center gap-6 self-center md:self-auto">
              <div
                className="w-32 h-32 sm:w-36 sm:h-36 rounded-full flex flex-col items-center justify-center border-4 shadow-inner text-center bg-white"
                style={{ borderColor: aqiColor }}
              >
                <span className="text-4xl sm:text-5xl font-black" style={{ color: aqiColor }}>
                  {aqiVal ?? "--"}
                </span>
                <span
                  className="mt-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold text-white uppercase tracking-wider"
                  style={{ backgroundColor: aqiColor }}
                >
                  {aqiLabel}
                </span>
              </div>

              <div className="space-y-2 text-xs text-gray-600">
                <div className="bg-gray-50 p-2.5 rounded-xl border border-gray-200">
                  <div className="text-gray-600 font-medium">PM2.5 (Latest)</div>
                  <div className="text-sm font-bold text-gray-900">
                    {latest.pm25 !== null && latest.pm25 !== undefined ? `${latest.pm25.toFixed(1)} μg/m³` : "N/A"}
                  </div>
                </div>
                <div className="bg-gray-50 p-2.5 rounded-xl border border-gray-200">
                  <div className="text-gray-600 font-medium">PM10 (Latest)</div>
                  <div className="text-sm font-bold text-gray-900">
                    {latest.pm10 !== null && latest.pm10 !== undefined ? `${latest.pm10.toFixed(1)} μg/m³` : "N/A"}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-100 flex flex-wrap items-center justify-between text-xs text-gray-600 gap-2">
            <span>24h Validity: {live.hours_24h} of 24 hours recorded</span>
            <span>Ground Station Ratio: {((live.ground_share_24h || 0) * 100).toFixed(0)}%</span>
            <span>Updated: {latest.ts ? new Date(latest.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "N/A"} IST</span>
          </div>
        </section>

        {/* 5-Day Festival-Aware AI Forecast */}
        <section className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 mb-8 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 mb-1">
                <span>🤖 Festival-Aware Gradient Boosting Model</span>
              </div>
              <h2 className="text-xl font-bold text-gray-900">
                5-Day AI Air Quality Forecast
              </h2>
            </div>
            <span className="text-xs text-gray-600 italic">
              Features: Time-of-year + Seasonal Inversions + Diwali/Holi signed distance + Stubble burning
            </span>
          </div>

          {/* Upcoming Festival Notice */}
          {forecast5d?.upcoming_festivals?.length > 0 && (
            <div className="mb-6 p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 flex items-center gap-2">
              <span className="text-base">🎆</span>
              <div>
                <span className="font-bold">Upcoming Festival Trigger: </span>
                {forecast5d.upcoming_festivals.map((f, i) => (
                  <span key={f.festival}>
                    {f.festival.toUpperCase()} in {f.in_days} days ({f.date})
                    {i < forecast5d.upcoming_festivals.length - 1 ? ", " : ""}
                  </span>
                ))}
                <span> — the model accounts for anticipated celebratory firecracker surges.</span>
              </div>
            </div>
          )}

          {forecast5d && forecast5d.days?.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 sm:gap-4">
              {forecast5d.days.map((d) => {
                const dayDate = new Date(d.date);
                const weekday = dayDate.toLocaleDateString("en-IN", { weekday: "short" });
                const monthDay = dayDate.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
                const cardColor = d.color || "#BDBDBD";

                return (
                  <div
                    key={d.date}
                    className="p-4 rounded-xl border border-gray-200 flex flex-col justify-between bg-white text-center hover:shadow-sm transition"
                  >
                    <div>
                      <div className="font-bold text-gray-900 text-sm">{weekday}</div>
                      <div className="text-xs text-gray-600 mb-2">{monthDay}</div>

                      <div className="my-2">
                        <span className="text-2xl font-black" style={{ color: cardColor }}>
                          {d.aqi ?? "--"}
                        </span>
                      </div>

                      <span
                        className="px-2 py-0.5 rounded text-[10px] font-bold text-white uppercase tracking-wider inline-block"
                        style={{ backgroundColor: cardColor }}
                      >
                        {d.label}
                      </span>
                    </div>

                    <div className="mt-4 pt-3 border-t border-gray-100 text-[11px] text-gray-600 space-y-1">
                      <div>PM2.5: <span className="font-semibold text-gray-800">{d.pm25} μg/m³</span></div>
                      <div className="text-[10px] text-gray-600">
                        80% Range: {d.aqi_low ?? "?"} - {d.aqi_high ?? "?"}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-6 bg-gray-50 border border-gray-200 rounded-xl text-center text-sm text-gray-500">
              5-day forecast points have not been precomputed for {place.name} yet. Nightly model training runs automatically.
            </div>
          )}

          {forecast5d?.note && (
            <p className="mt-4 text-xs text-gray-600 leading-relaxed italic border-t border-gray-100 pt-3">
              * {forecast5d.note}
            </p>
          )}
        </section>

        {/* Extended Seasonal Outlook (Days 6 to 30) */}
        {forecast30d && forecast30d.days?.length > 0 && (
          <section className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 mb-8 shadow-sm">
            <div className="mb-4">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 mb-1">
                <span>📅 Days 6 - 30 Situational Outlook</span>
              </div>
              <h2 className="text-xl font-bold text-gray-900">
                Extended Seasonal Baseline
              </h2>
              <p className="text-xs text-gray-600 mt-1">
                {forecast30d.note}
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-gray-200 text-gray-600 font-semibold uppercase">
                    <th className="py-2.5 px-3">Date</th>
                    <th className="py-2.5 px-3">Expected PM2.5</th>
                    <th className="py-2.5 px-3">Expected AQI</th>
                    <th className="py-2.5 px-3">Typical Range (25th - 75th %)</th>
                    <th className="py-2.5 px-3">Category</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {forecast30d.days.map((r) => {
                    const rowColor = r.color || "#BDBDBD";
                    return (
                      <tr key={r.date} className="hover:bg-gray-50">
                        <td className="py-2.5 px-3 font-medium text-gray-900">{r.date}</td>
                        <td className="py-2.5 px-3 text-gray-700">{r.pm25} μg/m³</td>
                        <td className="py-2.5 px-3 font-bold" style={{ color: rowColor }}>
                          {r.aqi ?? "--"}
                        </td>
                        <td className="py-2.5 px-3 text-gray-600">
                          AQI {r.aqi_low ?? "?"} – {r.aqi_high ?? "?"}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className="px-2 py-0.5 rounded text-[10px] font-bold text-white uppercase"
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
          </section>
        )}

        {/* Health Advisory Card */}
        <section className="bg-emerald-50/60 border border-emerald-200 rounded-2xl p-6 sm:p-8">
          <div className="flex items-start gap-4">
            <span className="text-3xl">🩺</span>
            <div>
              <h3 className="text-lg font-bold text-gray-900">
                Health Recommendation for Current AQI ({aqiLabel})
              </h3>
              <p className="text-sm text-gray-700 mt-1 leading-relaxed">
                {aqiVal <= 100 ? (
                  "Air quality is generally acceptable. Outdoor activities are safe for most individuals. Sensitive persons with severe asthma may observe mild symptoms."
                ) : aqiVal <= 200 ? (
                  "Children, elderly, and individuals with asthma or heart conditions should reduce heavy outdoor exertion. Keep prescribed inhalers handy."
                ) : aqiVal <= 300 ? (
                  "Prolonged outdoor exposure can cause respiratory discomfort. Wearing a certified N95 mask is advised for prolonged outdoor travel. Keep windows closed during rush hours."
                ) : (
                  "Severe pollution warning: Everyone may experience noticeable respiratory effects. Avoid heavy outdoor physical activity. Use indoor air purifiers and sealed N95/FFP2 masks outdoors."
                )}
              </p>
              <div className="mt-3">
                <Link to="/about" className="text-xs font-semibold text-emerald-800 hover:underline">
                  View complete medical standards and WHO vs CPCB comparisons →
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
