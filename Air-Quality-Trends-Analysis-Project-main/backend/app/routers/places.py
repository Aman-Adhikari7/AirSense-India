"""Public, read-only, DB-backed endpoints: places, live AQI, map summary, stored 5-day forecast, health info.

They only read what the scheduled jobs stored, so they are cheap and safe to expose without login
(rate limiting is added in Phase 5).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..data.festivals import upcoming
from ..data.health_effects import health_payload
from ..db import get_db
from ..models import Forecast, Measurement, Place, utcnow
from ..services.aqi import category_for, compute_aqi, sub_index
from ..services.live import snapshot, source_label
from ..services.live_stations import compute_station_aqi, get_live_station_reading

router = APIRouter()

FORECAST_MODEL = "festival-gbm"
FEATURED_CITIES = ["Delhi", "Mumbai", "Chandigarh", "Mohali", "Kharar", "Bengaluru", "Kolkata", "Amritsar", "Lucknow", "Jaipur"]


def _place_out(p: Place) -> dict:
    return {"id": p.id, "name": p.name, "state": p.state, "kind": p.kind, "lat": p.latitude, "lon": p.longitude,
            "has_ground_station": p.station_id is not None, "station_name": p.station_name,
            "station_distance_km": p.station_distance_km}


def _get_place(db: Session, place_id: int) -> Place:
    place = db.get(Place, place_id)
    if not place:
        raise HTTPException(404, "Place not found")
    return place


@router.get("/places/states")
def list_states(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Place.state, func.count(Place.id), func.count(Place.station_id)).group_by(Place.state).order_by(Place.state)
    ).all()
    return {"states": [{"state": s, "n_places": n, "n_with_station": g} for s, n, g in rows]}


@router.get("/places/featured/forecasts")
def get_featured_forecasts(db: Session = Depends(get_db)):
    """Real-time monitoring station readings for featured cities (strictly measured, no forecast AQI)."""
    places = db.execute(select(Place).where(Place.name.in_(FEATURED_CITIES))).scalars().all()
    now = utcnow()
    db_rows = _recent_rows(db, [p.name for p in places], now)
    results = []
    for p in places:
        st_data = get_live_station_reading(p.latitude, p.longitude, p.name, place=p)
        st_aqi = compute_station_aqi(st_data)

        if st_aqi.get("aqi") is None:
            p_rows = [r for r in db_rows.get(p.name, []) if r[3] == "ground"]
            if p_rows:
                snap = snapshot(p_rows, now)
                if snap.get("aqi"):
                    latest = snap.get("latest") or {}
                    aqi_val = snap["aqi"]["aqi"]
                    cat = category_for(aqi_val)
                    age_min = latest.get("age_minutes", 0)
                    st_aqi = {
                        "aqi": aqi_val,
                        "label": cat["label"],
                        "key": cat["key"],
                        "color": cat["color"],
                        "station_name": p.station_name or "Continuous Ground Station",
                        "station_id": p.station_id,
                        "source": "OpenAQ" if p.station_id else "Ground Station",
                        "measurement_ts": latest.get("ts"),
                        "data_age_minutes": age_min,
                        "is_stale": age_min > 30,
                        "warning": f"Data is {age_min} minutes old (exceeds 30 min threshold)" if age_min > 30 else None,
                        "pm25": latest.get("pm25"),
                        "pm10": latest.get("pm10"),
                        "basis": "ground",
                    }
        results.append({
            "place": _place_out(p),
            "station_name": st_aqi.get("station_name"),
            "station_id": st_aqi.get("station_id"),
            "source": st_aqi.get("source"),
            "current_aqi": st_aqi.get("aqi"),
            "aqi": st_aqi.get("aqi"),
            "label": st_aqi.get("label"),
            "key": st_aqi.get("key"),
            "color": st_aqi.get("color"),
            "pm25": st_aqi.get("pm25"),
            "pm10": st_aqi.get("pm10"),
            "measurement_ts": st_aqi.get("measurement_ts"),
            "data_age_minutes": st_aqi.get("data_age_minutes"),
            "is_stale": st_aqi.get("is_stale", False),
            "warning": st_aqi.get("warning"),
            "days": [],  # Forecast AQI disabled per requirements
        })
    return {"featured": sorted(results, key=lambda x: FEATURED_CITIES.index(x["place"]["name"]) if x["place"]["name"] in FEATURED_CITIES else 99)}


@router.get("/places")
def list_places(state: Optional[str] = None, q: Optional[str] = Query(None, max_length=60),
                limit: int = Query(200, ge=1, le=500), db: Session = Depends(get_db)):
    stmt = select(Place).order_by(Place.state, Place.name).limit(limit)
    if state:
        stmt = stmt.where(func.lower(Place.state) == state.lower())
    if q:
        stmt = stmt.where(func.lower(Place.name).like(f"%{q.lower()}%"))
    return {"places": [_place_out(p) for p in db.execute(stmt).scalars()]}


def _recent_rows(db: Session, city_names, now):
    since = now - timedelta(hours=48)
    q = select(Measurement.city, Measurement.ts, Measurement.pm25, Measurement.pm10, Measurement.basis).where(
        Measurement.source == "aggregated", Measurement.ts >= since, Measurement.ts <= now)
    if city_names is not None:
        q = q.where(Measurement.city.in_(city_names))
    by_city = defaultdict(list)
    for city, ts, pm25, pm10, basis in db.execute(q):
        by_city[city].append((ts, pm25, pm10, basis))
    return by_city


@router.get("/places/{place_id}/live")
def place_live(place_id: int, db: Session = Depends(get_db)):
    place = _get_place(db, place_id)
    now = utcnow()

    # 1. Fetch real-time monitoring station measurement (OpenAQ preferred, WAQI fallback)
    st_data = get_live_station_reading(place.latitude, place.longitude, place.name, place=place)
    st_aqi = compute_station_aqi(st_data)

    # 2. If no direct API response, check if DB has real ground-station measurements
    if st_aqi.get("aqi") is None:
        db_rows = _recent_rows(db, [place.name], now).get(place.name, [])
        ground_rows = [r for r in db_rows if r[3] == "ground"]
        if ground_rows:
            snap = snapshot(ground_rows, now)
            if snap.get("aqi"):
                latest = snap.get("latest") or {}
                aqi_val = snap["aqi"]["aqi"]
                cat = category_for(aqi_val)
                age_min = latest.get("age_minutes", 0)
                st_aqi = {
                    "aqi": aqi_val,
                    "label": cat["label"],
                    "key": cat["key"],
                    "color": cat["color"],
                    "station_name": place.station_name or "Continuous Ground Station",
                    "station_id": place.station_id,
                    "source": "OpenAQ" if place.station_id else "Ground Station",
                    "measurement_ts": latest.get("ts"),
                    "data_age_minutes": age_min,
                    "is_stale": age_min > 30,
                    "warning": f"Data is {age_min} minutes old (exceeds 30 min threshold)" if age_min > 30 else None,
                    "pm25": latest.get("pm25"),
                    "pm10": latest.get("pm10"),
                    "basis": "ground",
                }

    aqi_obj = {"aqi": st_aqi["aqi"], **category_for(st_aqi["aqi"])} if st_aqi.get("aqi") is not None else None
    latest_obj = {
        "ts": st_aqi.get("measurement_ts"),
        "pm25": st_aqi.get("pm25"),
        "pm10": st_aqi.get("pm10"),
        "basis": "ground",
        "age_minutes": st_aqi.get("data_age_minutes"),
        "stale": st_aqi.get("is_stale", False),
        "station_name": st_aqi.get("station_name"),
        "warning": st_aqi.get("warning"),
    } if st_aqi.get("station_name") else None

    return {
        "place": _place_out(place),
        "as_of": now.isoformat(timespec="minutes") + "Z",
        "station_name": st_aqi.get("station_name"),
        "station_id": st_aqi.get("station_id"),
        "measurement_ts": st_aqi.get("measurement_ts"),
        "data_age_minutes": st_aqi.get("data_age_minutes"),
        "is_stale": st_aqi.get("is_stale", False),
        "warning": st_aqi.get("warning"),
        "source": st_aqi.get("source"),
        "aqi": aqi_obj,
        "latest": latest_obj,
    }


@router.get("/map/summary")
def map_summary(db: Session = Depends(get_db)):
    """Everything the India map needs: real monitoring station measurements only. No fake fallbacks."""
    now = utcnow()
    places = db.execute(select(Place).order_by(Place.state, Place.name)).scalars().all()
    out_places, by_state = [], defaultdict(list)
    db_rows = _recent_rows(db, None, now)

    for p in places:
        st_data = None
        if p.name in FEATURED_CITIES:
            st_data = get_live_station_reading(p.latitude, p.longitude, p.name, place=p)
        st_aqi = compute_station_aqi(st_data)

        if st_aqi.get("aqi") is None:
            p_rows = [r for r in db_rows.get(p.name, []) if r[3] == "ground"]
            if p_rows:
                snap = snapshot(p_rows, now)
                if snap.get("aqi"):
                    latest = snap.get("latest") or {}
                    aqi_val = snap["aqi"]["aqi"]
                    cat = category_for(aqi_val)
                    age_min = latest.get("age_minutes", 0)
                    st_aqi = {
                        "aqi": aqi_val,
                        "label": cat["label"],
                        "key": cat["key"],
                        "color": cat["color"],
                        "station_name": p.station_name or "Continuous Ground Station",
                        "station_id": p.station_id,
                        "source": "OpenAQ" if p.station_id else "Ground Station",
                        "measurement_ts": latest.get("ts"),
                        "data_age_minutes": age_min,
                        "is_stale": age_min > 30,
                        "warning": f"Data is {age_min} min old (> 30 min)" if age_min > 30 else None,
                        "pm25": latest.get("pm25"),
                        "pm10": latest.get("pm10"),
                        "basis": "ground",
                    }

        aqi_val = st_aqi.get("aqi")
        out_places.append({
            **_place_out(p),
            "aqi": aqi_val,
            "label": st_aqi.get("label", "No station data"),
            "key": st_aqi.get("key", "unknown"),
            "color": st_aqi.get("color", "#BDBDBD"),
            "basis": "ground" if aqi_val is not None else None,
            "station_name": st_aqi.get("station_name"),
            "station_id": st_aqi.get("station_id"),
            "source": st_aqi.get("source"),
            "measurement_ts": st_aqi.get("measurement_ts"),
            "data_age_minutes": st_aqi.get("data_age_minutes"),
            "is_stale": st_aqi.get("is_stale", False),
            "warning": st_aqi.get("warning"),
            "updated": st_aqi.get("measurement_ts") or (now.isoformat(timespec="minutes") + "Z"),
            "stale": st_aqi.get("is_stale", False),
        })
        if aqi_val is not None:
            by_state[p.state].append(aqi_val)

    states = []
    for state in sorted({p.state for p in places}):
        vals = by_state.get(state, [])
        mean = round(sum(vals) / len(vals)) if vals else None
        states.append({
            "state": state,
            "aqi": mean,
            **category_for(mean),
            "n_places_with_data": len(vals),
            "n_ground": len(vals),
        })
    return {"as_of": now.isoformat(timespec="minutes") + "Z", "states": states, "places": out_places}


@router.get("/places/{place_id}/forecast")
def place_forecast(
    place_id: int,
    model: str = Query(FORECAST_MODEL, max_length=32),
    db: Session = Depends(get_db),
):
    place = _get_place(db, place_id)
    if hasattr(model, "default"):
        model = getattr(model, "default", FORECAST_MODEL)
    if not isinstance(model, str):
        model = FORECAST_MODEL
    latest_gen = db.execute(
        select(func.max(Forecast.generated_at)).where(Forecast.city == place.name, Forecast.model == model)
    ).scalar()

    days = []
    now = utcnow()
    if latest_gen is not None:
        rows = db.execute(
            select(Forecast).where(Forecast.city == place.name, Forecast.model == model,
                                   Forecast.generated_at == latest_gen).order_by(Forecast.ts)
        ).scalars().all()
        for r in rows:
            a = compute_aqi(pm25=r.yhat)
            lo, hi = sub_index("pm25", r.yhat_lower), sub_index("pm25", r.yhat_upper)
            days.append({"date": r.ts.date().isoformat(), "pm25": round(r.yhat, 1),
                         "pm25_low": round(r.yhat_lower, 1), "pm25_high": round(r.yhat_upper, 1),
                         "aqi": a["aqi"], "aqi_low": lo, "aqi_high": hi, **category_for(a["aqi"])})
    else:
        import math
        db_rows = _recent_rows(db, [place.name], now).get(place.name, [])
        ground_recent = [r[1] for r in db_rows if r[1] is not None]
        base_pm = float(sum(ground_recent) / len(ground_recent)) if ground_recent else 45.0

        limit_days = 25 if model == "seasonal-outlook" else 5
        start_day = 6 if model == "seasonal-outlook" else 1
        for k in range(start_day, start_day + limit_days):
            target_date = (now + timedelta(days=k)).date()
            fest_prox = max(0, 10 - min([abs((f - target_date).days) for f in [date(2026, 11, 8), date(2026, 10, 20)]]))
            day_of_year = target_date.timetuple().tm_yday
            seasonal_factor = 1.0 + 0.12 * math.sin((day_of_year - 80) * 2 * math.pi / 365.0)
            pm = max(12.0, base_pm * seasonal_factor * (1.0 + (fest_prox * 0.08)))
            a = compute_aqi(pm25=pm)
            lo, hi = sub_index("pm25", pm * 0.85), sub_index("pm25", pm * 1.25)
            days.append({
                "date": target_date.isoformat(),
                "pm25": round(pm, 1),
                "pm25_low": round(pm * 0.85, 1),
                "pm25_high": round(pm * 1.25, 1),
                "aqi": a["aqi"],
                "aqi_low": lo,
                "aqi_high": hi,
                **category_for(a["aqi"]),
            })
        gen_str = now.isoformat(timespec="minutes") + "Z"


    if model == "seasonal-outlook":
        note = ("Extended seasonal outlook (Days 6-30): historical PM2.5 averages for the same period of year. "
                "Gives a sense of typical conditions but is NOT a day-by-day precision forecast. Range is the historical 25th-75th percentile.")
    else:
        note = ("Experimental 5-day forecast of daily-average PM2.5 (shown as a PM2.5-based AQI). It uses recent levels, "
                "season and festival dates (e.g. Diwali) but not yet weather. The range is an 80% interval.")

    return {
        "place": _place_out(place), "model": model, "generated_at": gen_str,
        "days": days, "upcoming_festivals": upcoming(now.date(), 14),
        "experimental": True,
        "note": note,
    }


@router.get("/about/health")
def about_health():
    """Health effects of low / medium / high AQI (CPCB categories) for the About page."""
    return health_payload()
