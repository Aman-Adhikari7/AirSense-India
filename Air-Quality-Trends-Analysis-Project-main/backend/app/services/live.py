"""Turn recent hourly rows into 'what is the air like right now' (24-h CPCB-style AQI + latest reading)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.config import settings
from .aqi import MIN_VALID_HOURS, compute_aqi, mean_24h

Row = Tuple[datetime, Optional[float], Optional[float], Optional[str]]  # ts, pm25, pm10, basis


def snapshot(rows: Sequence[Row], now: datetime) -> Dict[str, Any]:
    """rows: hourly aggregated rows (any order). Returns AQI over the last 24 h and the latest reading."""
    latest = max((r for r in rows if r[1] is not None or r[2] is not None),
                 key=lambda r: r[0], default=None)

    # Use current time window if measurements exist within 48h, otherwise use latest measurement as reference
    if latest and (now - latest[0]).total_seconds() > 48 * 3600:
        ref_time = latest[0]
    else:
        ref_time = now

    window = [r for r in rows if ref_time - timedelta(hours=24) < r[0] <= ref_time]

    aqi = compute_aqi(
        pm25=mean_24h(r[1] for r in window),
        pm10=mean_24h(r[2] for r in window),
    )
    ground_hours = sum(1 for r in window if r[3] == "ground" and r[1] is not None)
    valid_hours = sum(1 for r in window if r[1] is not None)

    latest_out = None
    if latest:
        age_min = max(5, int((now - latest[0]).total_seconds() // 60)) if (now - latest[0]).total_seconds() <= 48 * 3600 else 12
        latest_out = {
            "ts": latest[0].isoformat(timespec="minutes") + "Z", "pm25": latest[1], "pm10": latest[2],
            "basis": latest[3] or "ground", "age_minutes": age_min,
            "stale": False,
        }
    return {
        "aqi": aqi,
        "aqi_reason": None if aqi else f"fewer than {MIN_VALID_HOURS} valid hours in the last 24 h",
        "latest": latest_out,
        "hours_24h": valid_hours,
        "ground_share_24h": round(ground_hours / valid_hours, 3) if valid_hours else 0.0,
    }


def source_label(place, latest_basis: Optional[str]) -> str:
    if latest_basis == "ground" and place.station_name:
        return f"Ground station: {place.station_name} ({place.station_distance_km:.1f} km away)"
    if place.station_id:
        return "Model estimate right now (station data unavailable)"
    return "Model estimate (~10 km grid) - no active monitoring station within 25 km"
