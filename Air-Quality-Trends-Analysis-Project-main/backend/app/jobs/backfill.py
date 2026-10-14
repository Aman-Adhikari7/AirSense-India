"""One-off history backfill for model training:  python -m app.jobs.backfill [--from 2022-08-01] [--only ...]

* Model history: Open-Meteo air-quality API, one request per ~year, rolled up to IST daily means (basis='model').
* Ground history: OpenAQ /sensors/{id}/days for places with a station (basis='ground'; replaces model days).
UNVERIFIED LIVE: check the earliest date Open-Meteo serves for India and the day-boundary convention of OpenAQ days.
Run it on your machine or a CI job (it makes ~1 request per place per year + a few OpenAQ calls).
"""
import argparse
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select

from ..core.config import settings
from ..db import SessionLocal, init_db
from ..models import Place
from ..services.daily import daily_from_hourly, upsert_daily
from ..services.fetchers import openaq_v3
from ..services.places import seed_if_empty
from ..services.scraper import ensure_station, fetch_open_meteo, flatten_rows

logger = logging.getLogger("airq.backfill")


def _chunks(start: date, end: date, span_days: int = 365):
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=span_days - 1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def backfill_place(db, place: Place, start: date, end: date) -> dict:
    model_days = 0
    for a, b in _chunks(start, end):
        rows = flatten_rows(place.name, place.latitude, place.longitude,
                            fetch_open_meteo(place.latitude, place.longitude, a.isoformat(), b.isoformat()))
        hourly = [(datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S"), r["pm25"], r["pm10"], "model") for r in rows]
        daily = daily_from_hourly(hourly)
        model_days += upsert_daily(db, [{**d, "city": place.name, "place_id": place.id} for d in daily])

    ground_days = 0
    if settings.OPENAQ_API_KEY and ensure_station(db, place):
        s, e = datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time())
        pm25 = openaq_v3.fetch_sensor_days(place.pm25_sensor_id, s, e)
        pm10 = openaq_v3.fetch_sensor_days(place.pm10_sensor_id, s, e) if place.pm10_sensor_id else {}
        ground_days = upsert_daily(db, [
            {"city": place.name, "place_id": place.id, "day": ts.date(), "pm25": v, "pm10": pm10.get(ts),
             "n_hours": None, "basis": "ground"} for ts, v in sorted(pm25.items())])
    return {"model_days": model_days, "ground_days": ground_days}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2022-08-01")
    ap.add_argument("--only", type=lambda s: [x.strip() for x in s.split(",") if x.strip()])
    a = ap.parse_args()
    init_db()
    start, end = date.fromisoformat(a.start), date.today() - timedelta(days=1)
    with SessionLocal() as db:
        seed_if_empty(db)
        q = select(Place).order_by(Place.id)
        if a.only:
            q = q.where(Place.name.in_(a.only))
        for p in db.execute(q).scalars().all():
            try:
                logger.info("%s: %s", p.name, backfill_place(db, p, start, end))
            except Exception as e:
                db.rollback()
                logger.warning("%s failed: %s", p.name, e)
