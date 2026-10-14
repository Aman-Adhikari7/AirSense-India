"""Indian National AQI (CPCB, 2014) for PM2.5 and PM10.

Breakpoints verified against CPCB Table (PM10 / PM2.5, 24-hour averages, ug/m3):
  Good 0-50 | Satisfactory 51-100 | Moderate 101-200 | Poor 201-300 | Very Poor 301-400 | Severe 401-500

IMPORTANT LIMITATION: the official CPCB AQI uses up to 8 pollutants (needs >= 3, one of them PM).
We only have PM2.5/PM10, so our value is a *PM-based* index. It can read lower than the official
station AQI when NO2/O3/CO/SO2 dominate. The API always labels it as such.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

# (conc_lo, conc_hi, index_lo, index_hi). Continuous at the band edges; first band whose conc_hi >= C wins.
BREAKPOINTS: Dict[str, List[Tuple[float, float, int, int]]] = {
    "pm25": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
             (90, 120, 201, 300), (120, 250, 301, 400), (250, 380, 401, 500)],
    "pm10": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
             (250, 350, 201, 300), (350, 430, 301, 400), (430, 510, 401, 500)],
}

# (max AQI in band, key, label, colour) - green = good, yellow = middle, red = high (as requested).
CATEGORIES = [
    (50, "good", "Good", "#1E9E57"),
    (100, "satisfactory", "Satisfactory", "#8BC34A"),
    (200, "moderate", "Moderate", "#F4C20D"),
    (300, "poor", "Poor", "#F28C28"),
    (400, "very_poor", "Very Poor", "#D32F2F"),
    (500, "severe", "Severe", "#7B1113"),
]

MIN_VALID_HOURS = 16  # CPCB: a 24-h average needs at least 16 valid hourly values


def sub_index(pollutant: str, conc: Optional[float]) -> Optional[int]:
    """AQI sub-index for one pollutant concentration (ug/m3). None for missing/invalid input."""
    if conc is None or conc < 0:
        return None
    bands = BREAKPOINTS[pollutant]
    if conc >= bands[-1][1]:
        return 500
    for c_lo, c_hi, i_lo, i_hi in bands:
        if conc <= c_hi:
            if c_hi == c_lo:
                return i_hi
            # first band starts at index 0; later bands start at i_lo (51, 101, ...) just above the edge
            if i_lo == 0:
                return int(round(i_hi * conc / c_hi))
            return int(round((i_hi - i_lo) / (c_hi - c_lo) * (conc - c_lo) + i_lo))
    return 500


def category_for(aqi: Optional[float]) -> Dict[str, str]:
    if aqi is None:
        return {"key": "unknown", "label": "No data", "color": "#BDBDBD"}
    for max_aqi, key, label, color in CATEGORIES:
        if aqi <= max_aqi:
            return {"key": key, "label": label, "color": color}
    key, label, color = CATEGORIES[-1][1:]
    return {"key": key, "label": label, "color": color}


def compute_aqi(pm25: Optional[float] = None, pm10: Optional[float] = None) -> Optional[Dict]:
    """PM-based Indian AQI from 24-h mean concentrations. Returns None when neither is available."""
    subs = {"pm25": sub_index("pm25", pm25), "pm10": sub_index("pm10", pm10)}
    subs = {k: v for k, v in subs.items() if v is not None}
    if not subs:
        return None
    dominant = max(subs, key=subs.get)
    aqi = subs[dominant]
    return {
        "aqi": aqi,
        **category_for(aqi),
        "dominant": dominant,
        "sub_indices": subs,
        "basis": "PM-only (CPCB uses up to 8 pollutants; this can read lower than the official AQI)",
    }


def mean_24h(values: Iterable[Optional[float]], min_valid: int = MIN_VALID_HOURS) -> Optional[float]:
    """Mean of hourly values, or None if fewer than `min_valid` valid hours."""
    valid = [float(v) for v in values if v is not None]
    if len(valid) < min_valid:
        return None
    return sum(valid) / len(valid)
