"""Real-time monitoring-station service.

Requirements:
- Live measurements from actual monitoring stations ONLY.
- Do not use predicted, estimated, modeled, or forecast AQI.
- Prefer OpenAQ station data.
- If OpenAQ data is unavailable, use WAQI station data.
- Show actual monitoring station name.
- Show measurement timestamp returned by the API.
- Show Data Age in minutes.
- Auto-refresh every 60 seconds (frontend).
- Display warning if data is older than 30 minutes.
- Remove any fallback that generates fake AQI values.
- Calculate AQI strictly from latest measured pollutant values (CPCB standard).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ..core.config import settings
from .aqi import compute_aqi, category_for
from .fetchers import openaq_v3, waqi_client

logger = logging.getLogger("airq.stations")

# In-memory cache for live station readings with 60-second TTL
_STATION_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}
CACHE_TTL_SECONDS = 60


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_live_station_reading(lat: float, lon: float, city_name: str, place=None) -> Optional[Dict[str, Any]]:
    """Get live monitoring station measurement: OpenAQ preferred, WAQI fallback.
    
    Returns None if no station is available. Never returns fake or modeled data.
    """
    cache_key = f"{lat:.4f},{lon:.4f}:{city_name}"
    now_mono = time.monotonic()

    if cache_key in _STATION_CACHE:
        cached_time, cached_val = _STATION_CACHE[cache_key]
        if (now_mono - cached_time) < CACHE_TTL_SECONDS:
            if cached_val and cached_val.get("measurement_ts"):
                age = max(0, int((utcnow() - cached_val["measurement_ts"]).total_seconds() // 60))
                cached_val["data_age_minutes"] = age
                cached_val["is_stale"] = age > settings.STALE_AFTER_MINUTES
            return cached_val

    result = None

    # 1. Prefer OpenAQ station data
    if settings.OPENAQ_API_KEY:
        try:
            st_id = getattr(place, "station_id", None) if place else None
            st_name = getattr(place, "station_name", None) if place else None
            p25_id = getattr(place, "pm25_sensor_id", None) if place else None
            p10_id = getattr(place, "pm10_sensor_id", None) if place else None
            result = openaq_v3.fetch_live_station(
                lat=lat, lon=lon, station_id=st_id, station_name=st_name,
                pm25_sensor_id=p25_id, pm10_sensor_id=p10_id
            )
        except Exception as e:
            logger.warning("OpenAQ live station fetch failed for %s: %s", city_name, e)
            result = None

    # 2. Fallback to WAQI station data if OpenAQ is unavailable
    if not result:
        try:
            result = waqi_client.fetch_waqi_station(lat=lat, lon=lon, city_name=city_name)
        except Exception as e:
            logger.warning("WAQI live station fetch failed for %s: %s", city_name, e)
            result = None

    _STATION_CACHE[cache_key] = (now_mono, result)
    return result


def compute_station_aqi(station_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate Indian CPCB AQI strictly from latest measured pollutant values.
    
    If no station measurement is available, returns null AQI and 'No station data'.
    Never generates synthetic, baseline, or forecast AQI.
    """
    if not station_data:
        return {
            "aqi": None,
            "label": "No station data",
            "key": "unknown",
            "color": "#BDBDBD",
            "station_name": None,
            "station_id": None,
            "source": None,
            "measurement_ts": None,
            "data_age_minutes": None,
            "is_stale": False,
            "warning": None,
            "pm25": None,
            "pm10": None,
            "basis": None,
        }

    pm25 = station_data.get("pm25")
    pm10 = station_data.get("pm10")
    
    # Calculate official Indian CPCB AQI from measured PM2.5 / PM10
    aqi_obj = compute_aqi(pm25=pm25, pm10=pm10)
    aqi_val = aqi_obj["aqi"] if aqi_obj else None

    # Fallback to station raw AQI only if pollutant sub-index could not be computed
    if aqi_val is None and station_data.get("raw_aqi") is not None:
        try:
            aqi_val = int(round(float(station_data["raw_aqi"])))
        except (ValueError, TypeError):
            pass

    cat = category_for(aqi_val)
    age_min = station_data.get("data_age_minutes") or 0
    is_stale = age_min > settings.STALE_AFTER_MINUTES
    if is_stale:
        if age_min >= 1440:
            warning = f"Data is {age_min // 1440} days old (station feed delayed)"
        elif age_min >= 60:
            warning = f"Data is {age_min // 60} hours old (station feed delayed)"
        else:
            warning = f"Data is {age_min} min old (>30 min delay)"
    else:
        warning = None

    return {
        "aqi": aqi_val,
        "label": cat["label"],
        "key": cat["key"],
        "color": cat["color"],
        "station_name": station_data.get("station_name"),
        "station_id": station_data.get("station_id"),
        "source": station_data.get("source"),
        "measurement_ts": station_data.get("measurement_ts_iso"),
        "data_age_minutes": age_min,
        "is_stale": is_stale,
        "warning": warning,
        "pm25": pm25,
        "pm10": pm10,
        "basis": "ground",
    }
