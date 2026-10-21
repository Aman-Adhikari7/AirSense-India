import React, { useState } from "react";

export default function ForecastChart({ days = [], activeIndex = null, onSelectDay = () => {} }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!days || days.length === 0) return null;

  const currentIndex = hoverIndex !== null ? hoverIndex : activeIndex !== null ? activeIndex : 0;
  const currentDay = days[currentIndex] || days[0];

  // Canvas bounds
  const width = 680;
  const height = 240;
  const padLeft = 45;
  const padRight = 78;  // extra space for threshold labels on right
  const padTop = 30;
  const padBottom = 40;

  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  // Find min and max for scaling
  const allValues = days.flatMap((d) => [d.aqi || 0, d.aqi_high || d.aqi || 0, d.aqi_low || d.aqi || 0]);
  const minVal = Math.max(0, Math.min(...allValues) - 20);
  const maxVal = Math.max(220, Math.max(...allValues) + 30);

  const getY = (val) => {
    if (val === null || val === undefined) return chartH + padTop;
    const ratio = (val - minVal) / (maxVal - minVal || 1);
    return padTop + chartH - ratio * chartH;
  };

  const getX = (idx) => {
    if (days.length <= 1) return padLeft + chartW / 2;
    return padLeft + (idx / (days.length - 1)) * chartW;
  };

  // Generate SVG path for main AQI line
  const points = days.map((d, i) => ({ x: getX(i), y: getY(d.aqi), ...d }));
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");

  // Generate area under curve
  const areaPath = `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${(padTop + chartH).toFixed(1)} L ${points[0].x.toFixed(1)} ${(padTop + chartH).toFixed(1)} Z`;

  // Generate confidence band path (upper bound -> lower bound reversed)
  const upperPoints = days.map((d, i) => ({ x: getX(i), y: getY(d.aqi_high ?? d.aqi) }));
  const lowerPoints = days.map((d, i) => ({ x: getX(i), y: getY(d.aqi_low ?? d.aqi) })).reverse();
  const bandPath = [
    upperPoints.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" "),
    lowerPoints.map((p) => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" "),
    "Z",
  ].join(" ");

  // Threshold lines to display — short labels to avoid clipping
  const thresholds = [
    { val: 50, label: "Good", color: "#1E9E57" },
    { val: 100, label: "Satisf.", color: "#8BC34A" },
    { val: 200, label: "Moderate", color: "#F4C20D" },
    { val: 300, label: "Poor", color: "#F28C28" },
    { val: 400, label: "V.Poor", color: "#D32F2F" },
  ].filter((t) => t.val >= minVal && t.val <= maxVal);

  const activeP = points[currentIndex] || points[0];

  return (
    <div className="w-full bg-gradient-to-b from-gray-50/80 to-white rounded-2xl border border-gray-200/80 p-4 sm:p-5">
      {/* Top Header & Selected Point Spotlight */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="flex h-2.5 w-2.5 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-600"></span>
          </span>
          <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">
            AI Trajectory & Confidence Envelope
          </span>
        </div>

        {currentDay && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500 font-medium">Selected Day:</span>
            <span className="font-bold text-gray-900">
              {new Date(currentDay.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}
            </span>
            <span
              className="px-2 py-0.5 rounded-full text-[10px] font-bold text-white uppercase shadow-xs"
              style={{ backgroundColor: currentDay.color || "#059669" }}
            >
              AQI {currentDay.aqi} • {currentDay.label}
            </span>
            <span className="hidden sm:inline-block text-gray-400 text-[11px]">
              (PM2.5: {currentDay.pm25} μg/m³ • 80% CI: {currentDay.aqi_low}–{currentDay.aqi_high})
            </span>
          </div>
        )}
      </div>

      {/* SVG Responsive Container */}
      <div className="relative w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible select-none"
        >
          <defs>
            {/* Area Fill Gradient */}
            <linearGradient id="aqiAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={activeP.color || "#059669"} stopOpacity="0.35" />
              <stop offset="70%" stopColor={activeP.color || "#059669"} stopOpacity="0.08" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0.0" />
            </linearGradient>

            {/* Line Multi-Stop Gradient */}
            <linearGradient id="aqiLineGrad" x1="0" y1="0" x2="1" y2="0">
              {days.map((d, i) => (
                <stop
                  key={i}
                  offset={`${(i / (days.length - 1 || 1)) * 100}%`}
                  stopColor={d.color || "#059669"}
                />
              ))}
            </linearGradient>
          </defs>

          {/* Grid Horizontal Guide Lines */}
          {thresholds.map((t) => {
            const y = getY(t.val);
            return (
              <g key={t.val} className="transition-opacity duration-300">
                <line
                  x1={padLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  stroke={t.color}
                  strokeWidth="1"
                  strokeDasharray="4 4"
                  strokeOpacity="0.35"
                />
                <text
                  x={width - padRight + 4}
                  y={y + 3}
                  fontSize="8"
                  fontWeight="600"
                  fill={t.color}
                  opacity="0.85"
                >
                  {t.label}
                </text>
              </g>
            );
          })}

          {/* 80% Confidence Interval Shaded Band */}
          <path
            d={bandPath}
            fill={activeP.color || "#059669"}
            fillOpacity="0.12"
            className="transition-all duration-300"
          />

          {/* Area fill under trend curve */}
          <path d={areaPath} fill="url(#aqiAreaGrad)" className="transition-all duration-300" />

          {/* Main Trajectory Line */}
          <path
            d={linePath}
            fill="none"
            stroke="url(#aqiLineGrad)"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Vertical Crosshair Line for Active Point */}
          <line
            x1={activeP.x}
            y1={padTop - 8}
            x2={activeP.x}
            y2={padTop + chartH}
            stroke={activeP.color || "#059669"}
            strokeWidth="1.5"
            strokeDasharray="3 3"
            strokeOpacity="0.75"
          />

          {/* Data Points on Line */}
          {points.map((p, i) => {
            const isSelected = i === currentIndex;
            return (
              <g
                key={i}
                className="cursor-pointer"
                onMouseEnter={() => setHoverIndex(i)}
                onMouseLeave={() => setHoverIndex(null)}
                onClick={() => onSelectDay(i)}
              >
                {/* Large Invisible Hit Target for easy touching/clicking */}
                <circle cx={p.x} cy={p.y} r="18" fill="transparent" />

                {/* Outer Glow / Halo for Active Point */}
                {isSelected && (
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r="9"
                    fill={p.color || "#059669"}
                    fillOpacity="0.28"
                    className="animate-pulse"
                  />
                )}

                {/* Visible Data Dot */}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isSelected ? "6" : "4.5"}
                  fill="#ffffff"
                  stroke={p.color || "#059669"}
                  strokeWidth={isSelected ? "3" : "2"}
                  className="transition-all duration-200"
                />

                {/* AQI Numeric Label Above Dot */}
                <text
                  x={p.x}
                  y={p.y - 12}
                  textAnchor="middle"
                  fontSize={isSelected ? "11" : "9.5"}
                  fontWeight={isSelected ? "800" : "600"}
                  fill={isSelected ? p.color : "#374151"}
                >
                  {p.aqi}
                </text>

                {/* X-Axis Date / Day Label — skip some if too crowded */}
                {(days.length <= 10 || i % Math.ceil(days.length / 10) === 0 || i === days.length - 1) && (
                  <text
                    x={p.x}
                    y={padTop + chartH + 18}
                    textAnchor="middle"
                    fontSize="8.5"
                    fontWeight={isSelected ? "700" : "500"}
                    fill={isSelected ? "#111827" : "#6B7280"}
                  >
                    {new Date(p.date).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                    })}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend Footer */}
      <div className="flex flex-wrap items-center justify-between text-[11px] text-gray-500 mt-2 pt-2 border-t border-gray-100 gap-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-1 rounded bg-emerald-600 inline-block"></span>
            <span>Predicted AQI</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded bg-emerald-600/15 border border-emerald-600/30 inline-block"></span>
            <span>80% Model Confidence Interval</span>
          </div>
        </div>
        <span className="text-[10px] text-gray-400 italic">
          Hover or click any node to inspect telemetry
        </span>
      </div>
    </div>
  );
}
