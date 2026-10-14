"""Collect hourly PM2.5/PM10 for a place and store the aggregated series (naive UTC, hour-aligned)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import Measurement, utcnow

logger = logging.getLogger("airq")

UPSERT_CHUNK = 1000


def fetch_open_meteo(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    # timezone=GMT: every source must use UTC or hourly values cannot be merged correctly.
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "pm2_5,pm10",
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "GMT",
    }
    try:
        r = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.Timeout:
        raise RuntimeError("OpenMeteoTimeout: upstream timed out")
    except requests.RequestException as e:
        raise RuntimeError(f"OpenMeteoHTTP: {e}")


def flatten_rows(city: str, lat: float, lon: float, data: dict) -> List[Dict[str, Any]]:
    from .fetchers.normalize import make_row, parse_ts

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    pm25 = hourly.get("pm2_5")
    pm10 = hourly.get("pm10")
    rows = []
    for i, t in enumerate(times):
        ts = parse_ts(t)
        if ts is None:
            continue
        rows.append(make_row(
            ts=ts, city=city, latitude=lat, longitude=lon,
            pm25=None if pm25 is None else pm25[i],
            pm10=None if pm10 is None else pm10[i],
            source="open-meteo",
        ))
    return rows


def _to_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")


def _insert_for(db: Session):
    name = db.get_bind().dialect.name
    if name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(f"Unsupported database dialect: {name}")
    return insert


def upsert_rows(db: Session, rows: List[Dict[str, Any]], place_id: Optional[int] = None) -> int:
    """Idempotent insert-or-update keyed on (ts, city, source). Works on PostgreSQL and SQLite."""
    if not rows:
        return 0
    deduped: Dict[tuple, Dict[str, Any]] = {}
    for r in rows:
        ts = _to_dt(r["ts"])
        key = (ts, r["city"], r["source"])
        deduped[key] = {
            "ts": ts, "city": r["city"], "source": r["source"], "place_id": place_id,
            "latitude": r.get("latitude"), "longitude": r.get("longitude"),
            "pm25": r.get("pm25"), "pm10": r.get("pm10"), "basis": r.get("basis"),
        }
    values = list(deduped.values())

    insert = _insert_for(db)
    try:
        for i in range(0, len(values), UPSERT_CHUNK):
            stmt = insert(Measurement)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ts", "city", "source"],
                set_={
                    # never overwrite an existing value with NULL
                    "pm25": func.coalesce(stmt.excluded.pm25, Measurement.pm25),
                    "pm10": func.coalesce(stmt.excluded.pm10, Measurement.pm10),
                    "latitude": func.coalesce(stmt.excluded.latitude, Measurement.latitude),
                    "longitude": func.coalesce(stmt.excluded.longitude, Measurement.longitude),
                    "basis": func.coalesce(stmt.excluded.basis, Measurement.basis),
                },
            )
            db.execute(stmt, values[i:i + UPSERT_CHUNK])
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(values)


def ensure_station(db: Session, place) -> bool:
    """Discover (once per week) the nearest active ground station for a place. True if it has one."""
    from .fetchers import openaq_v3

    if not settings.OPENAQ_API_KEY:
        return place.station_id is not None
    fresh = place.station_checked_at and (utcnow() - place.station_checked_at) < timedelta(days=7)
    if fresh:
        return place.station_id is not None
    try:
        st = openaq_v3.find_station(float(place.latitude), float(place.longitude))
    except openaq_v3.OpenAQError as e:
        logger.warning("station lookup failed for %s: %s", place.name, e)
        return place.station_id is not None  # keep what we knew; retry next run
    place.station_checked_at = utcnow()
    if st:
        place.station_id, place.station_name = st["station_id"], st["name"]
        place.station_distance_km = st["distance_km"]
        place.pm25_sensor_id, place.pm10_sensor_id = st["pm25_sensor_id"], st["pm10_sensor_id"]
    else:
        place.station_id = place.station_name = place.station_distance_km = None
        place.pm25_sensor_id = place.pm10_sensor_id = None
    db.commit()
    return place.station_id is not None


def collect_place(db: Session, place, days: int) -> Dict[str, Any]:
    """Collect hourly data for a catalogue place strictly from ground monitoring stations (OpenAQ preferred, WAQI fallback)."""
    from .fetchers import openaq_v3, waqi_client
    from .fetchers.normalize import make_row

    lat, lon = float(place.latitude), float(place.longitude)
    now = utcnow()
    end = now.date()
    start = end - timedelta(days=days)

    ground_rows: List[Dict[str, Any]] = []

    # 1. Prefer OpenAQ station data
    if ensure_station(db, place) and settings.OPENAQ_API_KEY:
        try:
            ground_rows = openaq_v3.fetch_station_hourly_rows(
                place.name, lat, lon, place.pm25_sensor_id, place.pm10_sensor_id,
                datetime.combine(start, datetime.min.time()), now,
            )
        except openaq_v3.OpenAQError as e:
            logger.warning("OpenAQ ground data failed for %s: %s", place.name, e)

    # 2. Fallback to WAQI station data
    if not ground_rows and settings.WAQI_TOKEN:
        try:
            w_res = waqi_client.fetch_waqi_station(lat, lon, place.name)
            if w_res and (w_res.get("pm25") is not None or w_res.get("pm10") is not None):
                ts = w_res["measurement_ts"].replace(minute=0, second=0, microsecond=0)
                row = make_row(
                    ts=ts, city=place.name, latitude=lat, longitude=lon,
                    pm25=w_res.get("pm25"), pm10=w_res.get("pm10"), source="waqi"
                )
                row["basis"] = "ground"
                ground_rows = [row]
        except Exception as e:
            logger.warning("WAQI ground data failed for %s: %s", place.name, e)

    for r in ground_rows:
        r["basis"] = "ground"

    n = upsert_rows(db, ground_rows, place_id=place.id)
    return {"ground_hours": len(ground_rows), "stored": n, "basis": "ground"}


def _collect_and_upsert(db: Session, city: str, days: int, sources=None):
    from .places import resolve_place

    place = resolve_place(db, city)
    res = collect_place(db, place, days)
    counts = {"open-meteo": res["model_hours"], "openaq": res["ground_hours"], "aggregated": res["stored"]}
    return counts, (float(place.latitude), float(place.longitude))


def ensure_window_for_city(db: Session, city: str, days: int, sources=None):
    counts, coords = _collect_and_upsert(db, city, days, sources)
    return sum(counts.values()), coords


def ensure_window_for_city_with_counts(db: Session, city: str, days: int, sources=None):
    return _collect_and_upsert(db, city, days, sources)
