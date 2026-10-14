"""Daily means per place (day = IST calendar day). Used for long retention and model training."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DailyMeasurement, Measurement, Place, utcnow
from .aqi import MIN_VALID_HOURS

IST_OFFSET = timedelta(hours=5, minutes=30)


def to_ist_day(ts_utc: datetime) -> date:
    return (ts_utc + IST_OFFSET).date()


def _dialect_insert(db: Session):
    name = db.get_bind().dialect.name
    if name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(f"Unsupported database dialect: {name}")
    return insert


def upsert_daily(db: Session, rows: List[dict]) -> int:
    """rows: {city, place_id, day, pm25, pm10, n_hours, basis}. A 'ground' value is never replaced by a 'model' one."""
    if not rows:
        return 0
    existing: Dict[Tuple[str, date], str] = {}
    cities = {r["city"] for r in rows}
    days = [r["day"] for r in rows]
    for c, d, b in db.execute(
        select(DailyMeasurement.city, DailyMeasurement.day, DailyMeasurement.basis).where(
            DailyMeasurement.city.in_(cities), DailyMeasurement.day >= min(days), DailyMeasurement.day <= max(days))
    ):
        existing[(c, d)] = b
    keep = [r for r in rows if not (existing.get((r["city"], r["day"])) == "ground" and r["basis"] != "ground")]
    if not keep:
        return 0
    insert = _dialect_insert(db)
    for i in range(0, len(keep), 1000):
        stmt = insert(DailyMeasurement)
        stmt = stmt.on_conflict_do_update(
            index_elements=["city", "day"],
            set_={"pm25": stmt.excluded.pm25, "pm10": stmt.excluded.pm10, "n_hours": stmt.excluded.n_hours,
                  "basis": stmt.excluded.basis, "place_id": stmt.excluded.place_id},
        )
        db.execute(stmt, keep[i:i + 1000])
    db.commit()
    return len(keep)


def daily_from_hourly(hourly: Iterable[Tuple[datetime, Optional[float], Optional[float], Optional[str]]],
                      min_hours: int = MIN_VALID_HOURS) -> List[dict]:
    """[(ts_utc, pm25, pm10, basis)] -> daily means by IST day; days with < min_hours valid PM2.5 hours are dropped."""
    buckets: Dict[date, dict] = defaultdict(lambda: {"pm25": [], "pm10": [], "basis": []})
    for ts, pm25, pm10, basis in hourly:
        b = buckets[to_ist_day(ts)]
        if pm25 is not None:
            b["pm25"].append(pm25)
        if pm10 is not None:
            b["pm10"].append(pm10)
        if basis:
            b["basis"].append(basis)
    out = []
    for day, b in sorted(buckets.items()):
        if len(b["pm25"]) < min_hours:
            continue
        ground = sum(x == "ground" for x in b["basis"])
        out.append({
            "day": day, "pm25": sum(b["pm25"]) / len(b["pm25"]),
            "pm10": (sum(b["pm10"]) / len(b["pm10"])) if len(b["pm10"]) >= min_hours else None,
            "n_hours": len(b["pm25"]),
            "basis": "ground" if ground >= len(b["basis"]) / 2 and ground else "model",
        })
    return out


def rollup_place(db: Session, place: Place, since: datetime) -> int:
    """Roll hourly `measurements` (aggregated series) since `since` (UTC) up into daily rows."""
    rows = db.execute(
        select(Measurement.ts, Measurement.pm25, Measurement.pm10, Measurement.basis).where(
            Measurement.city == place.name, Measurement.source == "aggregated", Measurement.ts >= since,
            Measurement.ts <= utcnow())  # ignore model hours that are still in the future
    ).all()
    days = daily_from_hourly(rows)
    return upsert_daily(db, [{**d, "city": place.name, "place_id": place.id} for d in days])
