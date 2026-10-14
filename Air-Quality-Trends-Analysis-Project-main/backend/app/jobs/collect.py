"""Hourly collector:  python -m app.jobs.collect [--days 3] [--only Delhi,Mumbai] [--limit N]

For every catalogue place: fetch Open-Meteo (model) + the nearest OpenAQ ground station (if OPENAQ_API_KEY is set),
store the best-available hourly series, and roll yesterday/today up into daily rows.
Exit code 1 if more than half the places failed (so a scheduler/CI run turns red).
"""
import argparse
import logging
import sys
from datetime import timedelta

from sqlalchemy import select

from ..db import SessionLocal, init_db
from ..models import Place, utcnow
from ..services.daily import rollup_place
from ..services.places import seed_if_empty
from ..services.scraper import collect_place

from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("airq.collect")


def _process_one_place(place_id: int, days: int) -> bool:
    with SessionLocal() as db:
        p = db.get(Place, place_id)
        if not p:
            return False
        try:
            res = collect_place(db, p, days)
            rollup_place(db, p, utcnow() - timedelta(days=days + 1))
            logger.info("%s: %s", p.name, res)
            return True
        except Exception as e:
            db.rollback()
            logger.warning("%s failed: %s", p.name, e)
            return False


def run(days: int = 3, only=None, limit=None, workers: int = 8) -> dict:
    init_db()
    ok = failed = 0
    with SessionLocal() as db:
        seed_if_empty(db)
        q = select(Place.id).order_by(Place.id)
        if only:
            q = q.where(Place.name.in_(only))
        place_ids = [pid for pid in db.execute(q).scalars()][: limit or None]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_one_place, pid, days): pid for pid in place_ids}
        for future in as_completed(futures):
            if future.result():
                ok += 1
            else:
                failed += 1

    return {"ok": ok, "failed": failed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--only", type=lambda s: [x.strip() for x in s.split(",") if x.strip()])
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    summary = run(a.days, a.only, a.limit)
    print(summary)
    sys.exit(1 if summary["failed"] > (summary["ok"] + summary["failed"]) / 2 else 0)
