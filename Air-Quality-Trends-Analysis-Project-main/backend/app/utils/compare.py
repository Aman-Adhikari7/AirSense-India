from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Measurement, utcnow


def compare_logic(db: Session, cities: list[str], days: int):
    """KPIs per city over the last `days` days (aggregated series, PM2.5). Lower mean = cleaner."""
    days = int(days)
    now = utcnow()
    start = now - timedelta(days=days)

    by_city = {}
    for c in cities:
        rows = db.execute(
            select(Measurement.ts, Measurement.pm25, Measurement.pm10)
            .where(
                Measurement.city == c,
                Measurement.source == "aggregated",
                Measurement.ts >= start,
                Measurement.ts <= now,
            )
            .order_by(Measurement.ts)
        ).all()

        vals = [r.pm25 for r in rows if r.pm25 is not None]
        by_city[c] = {
            "n_points": len(rows),
            "mean_pm25": (sum(vals) / len(vals)) if vals else None,
            "min_pm25": min(vals) if vals else None,
            "max_pm25": max(vals) if vals else None,
        }

    has_vals = {c: v for c, v in by_city.items() if v["mean_pm25"] is not None}
    best = min(has_vals, key=lambda k: has_vals[k]["mean_pm25"]) if has_vals else None
    worst = max(has_vals, key=lambda k: has_vals[k]["mean_pm25"]) if has_vals else None
    return {"days": days, "byCity": by_city, "best": best, "worst": worst}
