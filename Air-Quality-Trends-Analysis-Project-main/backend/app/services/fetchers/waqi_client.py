"""WAQI (World Air Quality Index project - aqicn.org) Station API Client.

Used as fallback when OpenAQ station data is unavailable.
Endpoints:
  https://api.waqi.info/feed/geo:{lat};{lon}/?token={WAQI_TOKEN}
  https://api.waqi.info/feed/{city}/?token={WAQI_TOKEN}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import requests

from ...core.config import settings

logger = logging.getLogger("airq.waqi")

WAQI_BASE = "https://api.waqi.info"


def _parse_waqi_time(time_data: dict) -> datetime:
    """Parse WAQI time dict {'s': 'YYYY-MM-DD HH:MM:SS', 'tz': '+05:30', 'iso': '...'} to naive UTC."""
    if not isinstance(time_data, dict):
        return datetime.now(timezone.utc).replace(tzinfo=None)
    
    iso_str = time_data.get("iso")
    if iso_str:
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except Exception:
            pass
            
    s_str = time_data.get("s")
    if s_str:
        try:
            # Assume local time if tz provided, else UTC
            tz_str = time_data.get("tz")
            raw_dt = datetime.strptime(str(s_str)[:19], "%Y-%m-%d %H:%M:%S")
            # If tz like +05:30, adjust to UTC
            if tz_str and len(tz_str) >= 5 and tz_str[0] in ("+", "-"):
                sign = 1 if tz_str[0] == "+" else -1
                parts = tz_str[1:].split(":")
                hrs = int(parts[0])
                mins = int(parts[1]) if len(parts) > 1 else 0
                offset_secs = sign * (hrs * 3600 + mins * 60)
                from datetime import timedelta
                return raw_dt - timedelta(seconds=offset_secs)
            return raw_dt
        except Exception:
            pass
            
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fetch_waqi_station(lat: float, lon: float, city_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch live real-time monitoring station measurement from WAQI.
    
    Returns station name, measurement timestamp, data age in minutes, and measured pollutant values.
    Returns None if WAQI token is missing or if station data is unavailable.
    """
    token = settings.WAQI_TOKEN
    if not token:
        return None

    headers = {"User-Agent": "AirSenseIndia/1.0"}
    try:
        payload = None
        if city_name:
            # Query official city station feed directly
            clean_city = city_name.strip().lower()
            # Handle Tricity aliases if needed
            if clean_city in ["mohali", "kharar"]:
                clean_city = "chandigarh"
            cr = requests.get(f"{WAQI_BASE}/feed/{requests.utils.quote(clean_city)}/", params={"token": token}, headers=headers, timeout=8)
            if cr.status_code == 200 and cr.json().get("status") == "ok" and cr.json().get("data"):
                payload = cr.json()

        if not payload or payload.get("status") != "ok":
            url = f"{WAQI_BASE}/feed/geo:{lat:.4f};{lon:.4f}/"
            r = requests.get(url, params={"token": token}, headers=headers, timeout=8)
            if r.status_code == 200 and r.json().get("status") == "ok" and r.json().get("data"):
                payload = r.json()

        if not payload or payload.get("status") != "ok" or not payload.get("data"):
            return None

        data = payload.get("data")
        if not isinstance(data, dict):
            return None

        city_info = data.get("city") or {}
        st_name = city_info.get("name") or (f"{city_name} Station" if city_name else "Continuous Monitoring Station")
        st_id = data.get("idx")

        time_info = data.get("time") or {}
        measurement_ts = _parse_waqi_time(time_info)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        data_age_min = max(0, int((now_utc - measurement_ts).total_seconds() // 60))

        iaqi = data.get("iaqi") or {}
        pm25 = iaqi.get("pm25", {}).get("v") if isinstance(iaqi.get("pm25"), dict) else None
        pm10 = iaqi.get("pm10", {}).get("v") if isinstance(iaqi.get("pm10"), dict) else None

        raw_aqi = data.get("aqi")
        if isinstance(raw_aqi, (int, float)):
            raw_aqi = float(raw_aqi)
        else:
            raw_aqi = None

        return {
            "station_name": st_name,
            "station_id": st_id,
            "source": "WAQI",
            "measurement_ts": measurement_ts,
            "measurement_ts_iso": measurement_ts.isoformat(timespec="minutes") + "Z",
            "data_age_minutes": data_age_min,
            "is_stale": data_age_min > settings.STALE_AFTER_MINUTES,
            "pm25": float(pm25) if pm25 is not None else None,
            "pm10": float(pm10) if pm10 is not None else None,
            "raw_aqi": raw_aqi,
        }
    except Exception as e:
        logger.warning("WAQI fetch failed for (%.4f, %.4f): %s", lat, lon, e)
        return None
