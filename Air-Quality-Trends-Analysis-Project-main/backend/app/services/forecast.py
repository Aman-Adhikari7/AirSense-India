from __future__ import annotations
import hashlib
import os
import re
import time
from datetime import timedelta
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_absolute_error, mean_squared_error
from joblib import dump, load

from ..core.config import settings
from ..models import Measurement, utcnow

MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
os.makedirs(MODELS_DIR, exist_ok=True)

def _load_series(db: Session, city: str, days: int) -> pd.DataFrame:
    """Pull last N days of the aggregated series as an hourly pandas frame (pm2.5 is the target)."""
    now = utcnow()
    rows = db.execute(
        select(Measurement.ts, Measurement.pm25)
        .where(
            Measurement.city == city,
            Measurement.source == "aggregated",
            Measurement.ts >= now - timedelta(days=int(days)),
            Measurement.ts <= now,
        )
        .order_by(Measurement.ts)
    ).all()

    if not rows:
        raise ValueError(f"No data found for {city} in last {days} days. Run /scrape first.")

    df = pd.DataFrame(rows, columns=["ts", "pm25"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    # Ensure hourly frequency and fill small gaps
    df = df.asfreq("h")
    df["pm25"] = df["pm25"].astype(float).interpolate(limit_direction="both")

    return df  # columns: pm25 (float), index: hourly ts (naive UTC)

def _model_path(city: str) -> str:
    """Filesystem-safe model path. The city comes from users, so never use it raw in a path."""
    slug = re.sub(r"[^a-z0-9]+", "_", city.lower()).strip("_")[:40] or "city"
    digest = hashlib.sha1(city.lower().encode("utf-8")).hexdigest()[:10]
    return os.path.join(MODELS_DIR, f"{slug}_{digest}_sarimax.joblib")

def _cache_is_fresh(path: str) -> bool:
    if not os.path.exists(path):
        return False
    return (time.time() - os.path.getmtime(path)) < settings.MODEL_CACHE_HOURS * 3600

def train_sarimax(df: pd.DataFrame) -> SARIMAX:
    """
    Build a sensible default SARIMAX for hourly PM2.5.
    - Differencing (d=1) for trend
    - Seasonal weekly pattern for hourly data: 24*7=168
      -> seasonal order (P,D,Q,168)
    - Keep it modest to train fast.
    """
    # Basic sanity: drop any remaining NaNs
    y = df["pm25"].astype(float).ffill().bfill()

    # Try a simple configuration; tweak later if needed
    order = (1, 1, 1)
    seasonal_order = (1, 0, 1, 24)  # daily seasonality is often present; weekly = 168 if you have lots of data
    # If you have >= 14 days, consider (1,0,1,24) or (1,0,1,168); (24) is lighter.
    model = SARIMAX(y, order=order, seasonal_order=seasonal_order, enforce_stationarity=False, enforce_invertibility=False)
    return model

def fit_and_save_model(db: Session, city: str, train_days: int = 30) -> str:
    df = _load_series(db, city, days=train_days)
    model = train_sarimax(df)
    result = model.fit(disp=False)
    path = _model_path(city)
    dump(result, path)
    return path

def forecast_city(db: Session, city: str, horizon_days: int = 7, train_days: int = 30, use_cache: bool = True):
    """Fit (or load) a SARIMAX model and forecast H days ahead with CIs."""
    path = _model_path(city)
    result = None

    if use_cache and _cache_is_fresh(path):
        try:
            result = load(path)
        except Exception:
            result = None

    if result is None:
        # (Re)train
        df = _load_series(db, city, days=train_days)
        model = train_sarimax(df)
        result = model.fit(disp=False)
        dump(result, path)

    steps = int(horizon_days * 24)
    pred = result.get_forecast(steps=steps)
    mean = pred.predicted_mean
    ci = pred.conf_int(alpha=0.2)  # 80% CI looks good for charts; change if you like (95% => alpha=0.05)

    out = []
    for ts, yhat in mean.items():
        low = float(ci.loc[ts].iloc[0])
        high = float(ci.loc[ts].iloc[1])
        out.append({
            "ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "yhat": float(yhat),
            "yhat_lower": low,
            "yhat_upper": high
        })
    return {"city": city, "horizon_hours": steps, "series": out}

def backtest_roll(db: Session, city: str, days: int = 30, horizon_hours: int = 24):
    """
    Simple rolling-origin backtest: walk forward, forecast H hours, compute MAE/RMSE.
    Useful for a quick slide proving validity.
    """
    df = _load_series(db, city, days=days)
    y = df["pm25"].astype(float)
    # choose checkpoints every 24 hours to keep it fast
    checkpoints = list(range(24*7, len(y) - horizon_hours, 24))
    preds, trues = [], []

    for cut in checkpoints:
        train_y = y.iloc[:cut]
        model = SARIMAX(train_y, order=(1,1,1), seasonal_order=(1,0,1,24),
                        enforce_stationarity=False, enforce_invertibility=False)
        res = model.fit(disp=False)
        fc = res.get_forecast(steps=horizon_hours).predicted_mean
        true = y.iloc[cut:cut+horizon_hours]
        # align lengths (edge cases)
        n = min(len(fc), len(true))
        preds.extend(fc.iloc[:n].values)
        trues.extend(true.iloc[:n].values)

    mae = float(mean_absolute_error(trues, preds))
    rmse = float(np.sqrt(mean_squared_error(trues, preds)))
    return {"city": city, "days": days, "horizon_hours": horizon_hours, "mae": mae, "rmse": rmse}


# multi-cities forecaster
def forecast_cities(
        db: Session,
        cities: list[str],
        horizon_days: int = 7,
        train_days: int = 30,
        use_cache: bool = True,
):
    """
    Runs forecast_city for each city and returns a dict { city -> series }.
    Also returns a small summary (mean predicted pm25 per city) to pick best/worst.
    """
    results = {}
    summary = {}

    for city in cities:
        try:
            fc = forecast_city(db, city, horizon_days, train_days, use_cache)
            results[city] = fc["series"]
            # mean of yhat over the horizon for ranking
            vals = [p["yhat"] for p in fc["series"] if p.get("yhat") is not None]
            summary[city] = {
                "mean_yhat": (sum(vals) / len(vals)) if vals else None,
                "n_points": len(vals)
            }
        except Exception as e:
            results[city] = {"error": str(e)}
            summary[city] = {"mean_yhat": None, "n_points": 0}

    # pick best/worst by mean_yhat (lower is “cleaner”)
    valid = {c: s for c, s in summary.items() if s["mean_yhat"] is not None}
    best = min(valid, key=lambda c: valid[c]["mean_yhat"]) if valid else None
    worst = max(valid, key=lambda c: valid[c]["mean_yhat"]) if valid else None

    return {
        "byCity": results,
        "summary": summary,
        "best": best,
        "worst": worst
    }
