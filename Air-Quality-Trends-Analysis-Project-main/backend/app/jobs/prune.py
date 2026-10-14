"""Hourly data retention pruning job.

Usage:
  python -m app.jobs.prune [--keep-days 30]

Purpose:
  Keeps free PostgreSQL databases within size limits (< 500 MB) by safely
  purging raw hourly measurements older than `keep_days`.
  Important: Daily measurements (`daily_measurements`) are PRESERVED permanently
  for historical analysis and ML model training.
"""
from __future__ import annotations

import argparse
import logging
from datetime import timedelta

from sqlalchemy import delete, func, select

from ..db import SessionLocal, init_db
from ..models import Forecast, Measurement, utcnow

logger = logging.getLogger("airq.prune")


def prune_data(db, keep_days: int = 30) -> dict:
    now = utcnow()
    cutoff_measurements = now - timedelta(days=keep_days)
    cutoff_forecasts = now - timedelta(days=7)

    # 1. Prune old hourly measurements
    del_m = db.execute(
        delete(Measurement).where(Measurement.ts < cutoff_measurements)
    )
    m_count = del_m.rowcount if hasattr(del_m, "rowcount") else 0

    # 2. Prune old forecasts (keep only recent runs)
    del_f = db.execute(
        delete(Forecast).where(Forecast.generated_at < cutoff_forecasts)
    )
    f_count = del_f.rowcount if hasattr(del_f, "rowcount") else 0

    db.commit()
    logger.info("Pruned %d hourly measurements and %d old forecast records", m_count, f_count)
    return {
        "pruned_measurements": m_count,
        "pruned_forecasts": f_count,
        "measurements_cutoff": cutoff_measurements.isoformat(),
        "forecasts_cutoff": cutoff_forecasts.isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Prune old hourly measurements to keep DB size lean.")
    parser.add_argument("--keep-days", type=int, default=30, help="Days of hourly data to keep (default: 30)")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as session:
        result = prune_data(session, keep_days=args.keep_days)
        print(result)
