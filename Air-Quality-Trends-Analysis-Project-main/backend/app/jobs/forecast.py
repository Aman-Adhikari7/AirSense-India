"""Nightly forecast:  python -m app.jobs.forecast [--backtest-from 2025-01-01]

Trains the pooled festival-aware model on all daily history, predicts the next 5 days for every place and stores
the result in `forecasts` (model='festival-gbm'). --backtest-from prints honest accuracy vs naive baselines instead.
"""
import argparse
import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import delete, select

from ..db import SessionLocal, init_db
from ..models import DailyMeasurement, Forecast, Place, utcnow
from ..services.daily import IST_OFFSET
from ..services.festival_model import FestivalModel, backtest, build_training_frame, forecast_place
from ..services.seasonal_outlook import seasonal_forecast

logger = logging.getLogger("airq.forecast")
MODEL_NAME = "festival-gbm"
SEASONAL_MODEL_NAME = "seasonal-outlook"


def load_series(db):
    series, lats, places = {}, {}, {}
    for p in db.execute(select(Place)).scalars():
        rows = db.execute(select(DailyMeasurement.day, DailyMeasurement.pm25)
                          .where(DailyMeasurement.city == p.name).order_by(DailyMeasurement.day)).all()
        if len(rows) < 40:
            continue
        s = pd.Series({pd.Timestamp(d): v for d, v in rows}, dtype=float)
        series[p.name] = s.asfreq("D")  # missing days -> NaN (never invented)
        lats[p.name], places[p.name] = p.latitude, p
    return series, lats, places


def run(db, today_ist: Optional[date] = None) -> dict:
    series, lats, places = load_series(db)
    if not series:
        raise ValueError("No daily history yet. Run the collector and the backfill first.")
    frame = build_training_frame(series, lats)
    model = FestivalModel.fit(frame)
    today_ist = today_ist or (utcnow() + IST_OFFSET).date()
    origin = pd.Timestamp(today_ist - timedelta(days=1))  # last complete IST day
    now, stored, skipped = utcnow(), 0, 0
    for name, s in series.items():
        fc = forecast_place(model, s, lats[name], origin)
        if not fc:
            skipped += 1
            continue
        db.execute(delete(Forecast).where(Forecast.city == name, Forecast.model == MODEL_NAME))
        db.add_all([Forecast(city=name, place_id=places[name].id, model=MODEL_NAME, generated_at=now,
                             ts=datetime.combine(f["day"], datetime.min.time()), yhat=f["yhat"],
                             yhat_lower=f["yhat_lower"], yhat_upper=f["yhat_upper"]) for f in fc])
        stored += len(fc)
    db.commit()
    return {"places": len(series) - skipped, "skipped": skipped, "rows": stored, "train_samples": int(len(frame))}


def run_seasonal_outlook(db, today_ist: Optional[date] = None) -> dict:
    series, lats, places = load_series(db)
    if not series:
        raise ValueError("No daily history yet. Run the collector and backfill first.")
    today_ist = today_ist or (utcnow() + IST_OFFSET).date()
    origin = pd.Timestamp(today_ist - timedelta(days=1))
    now, stored, skipped = utcnow(), 0, 0
    for name, s in series.items():
        if len(s.dropna()) < 60:
            skipped += 1
            continue
        fc = seasonal_forecast(s, origin)
        if not fc:
            skipped += 1
            continue
        db.execute(delete(Forecast).where(Forecast.city == name, Forecast.model == SEASONAL_MODEL_NAME))
        db.add_all([Forecast(city=name, place_id=places[name].id, model=SEASONAL_MODEL_NAME, generated_at=now,
                             ts=datetime.combine(f["day"], datetime.min.time()), yhat=f["yhat"],
                             yhat_lower=f["yhat_lower"], yhat_upper=f["yhat_upper"]) for f in fc])
        stored += len(fc)
    db.commit()
    return {"places": len(series) - skipped, "skipped": skipped, "rows": stored}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest-from", help="YYYY-MM-DD: train before, test after; prints accuracy vs baselines")
    ap.add_argument("--seasonal-only", action="store_true", help="Run only the 6-30 day seasonal outlook")
    a = ap.parse_args()
    init_db()
    with SessionLocal() as db:
        if a.backtest_from:
            series, lats, _ = load_series(db)
            print(json.dumps(backtest(build_training_frame(series, lats), pd.Timestamp(a.backtest_from)), indent=2))
        elif a.seasonal_only:
            print(run_seasonal_outlook(db))
        else:
            res_gbm = run(db)
            try:
                res_seasonal = run_seasonal_outlook(db)
            except Exception as e:
                res_seasonal = {"error": str(e)}
            print(json.dumps({"festival_gbm": res_gbm, "seasonal_outlook": res_seasonal}, indent=2))
