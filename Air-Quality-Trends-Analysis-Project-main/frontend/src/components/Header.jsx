import React from "react";
import { Link, useLocation } from "react-router-dom";

export default function Header() {
  const location = useLocation();

  const navItems = [
    { label: "India Map & Overview", path: "/" },
    { label: "Search Stations", path: "/search" },
    { label: "About & Health Guide", path: "/about" },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group">
          <span className="text-2xl" role="img" aria-label="leaf">🌿</span>
          <div className="flex flex-col">
            <span className="text-xl font-bold tracking-tight text-emerald-800 group-hover:text-emerald-700 transition-colors">
              AirSense India
            </span>
            <span className="text-xs text-gray-700 -mt-1 font-medium">
              National Air Quality & 5-Day Forecast
            </span>
          </div>
        </Link>

        <nav className="flex items-center gap-1 sm:gap-2">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-emerald-50 text-emerald-800 font-semibold"
                    : "text-gray-600 hover:text-emerald-700 hover:bg-gray-50"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
