"""OpenAQ v3 client (ground monitoring stations, ug/m3). Needs a free API key (header X-API-Key).

Endpoints used - /v3/locations (verified in docs.openaq.org: coordinates=lat,lon, radius<=25000, parameters_id, X-API-Key),
/v3/locations/{id}/latest (verified), /v3/sensors/{id}/hours and /v3/sensors/{id}/days (paths taken from the docs'
operation names; response parsing is defensive).  # UNVERIFIED LIVE - see PROGRESS.md "verify first".
Rate limit (free key): 60 req/min, 2000 req/hour -> we sleep between calls (OPENAQ_MIN_INTERVAL_S).
"""
from __future__ import annotations

import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from ...core.config import settings

logger = logging.getLogger("airq")

BASE = "https://api.openaq.org/v3"
PM25_PARAM_ID = 2  # confirmed by OpenAQ docs example (parameters/2/latest = PM2.5)
_last_call = 0.0


class OpenAQError(RuntimeError):
    pass


def _get(path: str, params: Optional[dict] = None) -> dict:
    global _last_call
    if not settings.OPENAQ_API_KEY:
        raise OpenAQError("OPENAQ_API_KEY is not set")
    min_gap = float(os.getenv("OPENAQ_MIN_INTERVAL_S", "1.1"))  # stay under 60 req/min
    wait = min_gap - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}{path}", params=params, headers={"X-API-Key": settings.OPENAQ_API_KEY}, timeout=30)
            _last_call = time.monotonic()
            if r.status_code == 429:  # rate limited: back off and retry
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == 2:
                raise OpenAQError(f"OpenAQ request failed: {e}")
            time.sleep(2 * (attempt + 1))
    raise OpenAQError("OpenAQ rate limit: retries exhausted")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _utc(obj: Any) -> Optional[datetime]:
    """{'utc': '...Z', 'local': '...'} or an ISO string -> naive UTC datetime."""
    s = obj.get("utc") if isinstance(obj, dict) else obj
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d


def find_station(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Nearest *active* station within STATION_RADIUS_M that measures PM2.5. None if there is none."""
    data = _get("/locations", {
        "coordinates": f"{lat:.4f},{lon:.4f}", "radius": settings.STATION_RADIUS_M,
        "parameters_id": PM25_PARAM_ID, "limit": 100,
    })
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    best = None
    for loc in data.get("results") or []:
        coords = loc.get("coordinates") or {}
        if "latitude" not in coords or "longitude" not in coords:
            continue
        last = _utc(loc.get("datetimeLast"))
        if last is not None and (now - last) > timedelta(days=settings.STATION_MAX_AGE_DAYS):
            continue  # dead station
        sensors = {}
        for s in loc.get("sensors") or []:
            pname = ((s.get("parameter") or {}).get("name") or "").lower()
            if pname in ("pm25", "pm10"):
                sensors[pname] = s.get("id")
        if "pm25" not in sensors:
            continue
        dist = haversine_km(lat, lon, coords["latitude"], coords["longitude"])
        if best is None or dist < best["distance_km"]:
            best = {"station_id": loc["id"], "name": loc.get("name"), "distance_km": round(dist, 2),
                    "pm25_sensor_id": sensors["pm25"], "pm10_sensor_id": sensors.get("pm10")}
    return best


def _paged(path: str, params: dict, max_pages: int = 20) -> List[dict]:
    out: List[dict] = []
    limit = int(params.get("limit", 1000))
    for page in range(1, max_pages + 1):
        res = (_get(path, {**params, "page": page}).get("results")) or []
        out.extend(res)
        if len(res) < limit:
            break
    return out


def _period_start(item: dict) -> Optional[datetime]:
    period = item.get("period") or {}
    return _utc(period.get("datetimeFrom")) or _utc(period.get("datetimeTo"))


def fetch_sensor_hours(sensor_id: int, start: datetime, end: datetime) -> Dict[datetime, float]:
    """Hourly means for one sensor -> {naive-UTC hour: value}. Negative values (sensor faults) dropped."""
    rows = _paged(f"/sensors/{sensor_id}/hours", {
        "datetime_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datetime_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": 1000,
    })
    out: Dict[datetime, float] = {}
    for it in rows:
        ts, v = _period_start(it), it.get("value")
        if ts is not None and isinstance(v, (int, float)) and v >= 0:
            out[ts.replace(minute=0, second=0, microsecond=0)] = float(v)
    return out


def fetch_sensor_days(sensor_id: int, start: datetime, end: datetime) -> Dict[datetime, float]:
    """Daily means (UTC days) for one sensor -> {day start: value}. Used for multi-year backfill."""
    rows = _paged(f"/sensors/{sensor_id}/days", {
        "datetime_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datetime_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": 1000,
    })
    out: Dict[datetime, float] = {}
    for it in rows:
        ts, v = _period_start(it), it.get("value")
        if ts is not None and isinstance(v, (int, float)) and v >= 0:
            out[ts] = float(v)
    return out


def fetch_station_hourly_rows(place_name: str, lat: float, lon: float, pm25_sensor: int,
                              pm10_sensor: Optional[int], start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """Rows shaped like the Open-Meteo rows (source='openaq'), merged on the hour."""
    from .normalize import make_row
    pm25 = fetch_sensor_hours(pm25_sensor, start, end)
    pm10 = fetch_sensor_hours(pm10_sensor, start, end) if pm10_sensor else {}
    return [
        make_row(ts, place_name, lat, lon, pm25.get(ts), pm10.get(ts), "openaq")
        for ts in sorted(set(pm25) | set(pm10))
    ]


def fetch_latest(station_id: int) -> Dict[int, Dict[str, Any]]:
    """Latest reading per sensor id: {sensor_id: {'value', 'ts'}} (ts = naive UTC)."""
    data = _get(f"/locations/{station_id}/latest", {"limit": 100})
    out: Dict[int, Dict[str, Any]] = {}
    for it in data.get("results") or []:
        sid, v, ts = it.get("sensorsId"), it.get("value"), _utc(it.get("datetime"))
        if sid is not None and isinstance(v, (int, float)) and v >= 0 and ts is not None:
            out[int(sid)] = {"value": float(v), "ts": ts}
    return out


def fetch_live_station(
    lat: float,
    lon: float,
    station_id: Optional[int] = None,
    station_name: Optional[str] = None,
    pm25_sensor_id: Optional[int] = None,
    pm10_sensor_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch live real-time measurement from OpenAQ monitoring station."""
    if not settings.OPENAQ_API_KEY:
        return None

    st_id = station_id
    st_name = station_name
    p25_id = pm25_sensor_id
    p10_id = pm10_sensor_id

    if not st_id:
        st = find_station(lat, lon)
        if not st:
            return None
        st_id = st["station_id"]
        st_name = st["name"]
        p25_id = st.get("pm25_sensor_id")
        p10_id = st.get("pm10_sensor_id")

    readings = fetch_latest(st_id)
    if not readings:
        return None

    pm25_val = None
    pm10_val = None
    latest_ts = None

    if p25_id and p25_id in readings:
        pm25_val = readings[p25_id]["value"]
        latest_ts = readings[p25_id]["ts"]
    if p10_id and p10_id in readings:
        pm10_val = readings[p10_id]["value"]
        if latest_ts is None or readings[p10_id]["ts"] > latest_ts:
            latest_ts = readings[p10_id]["ts"]

    # If specific sensor IDs weren't matched, check any sensor reading
    if pm25_val is None and readings:
        for it in readings.values():
            if latest_ts is None or it["ts"] > latest_ts:
                latest_ts = it["ts"]

    if latest_ts is None:
        return None

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    data_age_min = max(0, int((now_utc - latest_ts).total_seconds() // 60))

    return {
        "station_name": st_name or "Continuous Air Monitoring Station",
        "station_id": st_id,
        "source": "OpenAQ",
        "measurement_ts": latest_ts,
        "measurement_ts_iso": latest_ts.isoformat(timespec="minutes") + "Z",
        "data_age_minutes": data_age_min,
        "is_stale": data_age_min > settings.STALE_AFTER_MINUTES,
        "pm25": float(pm25_val) if pm25_val is not None else None,
        "pm10": float(pm10_val) if pm10_val is not None else None,
        "raw_aqi": None,
    }

