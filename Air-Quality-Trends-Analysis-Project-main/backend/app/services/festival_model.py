"""5-day PM2.5 forecast that knows about festivals (Diwali, Dussehra, Holi, New Year) and the stubble-burning season.

Design (honest by construction)
-------------------------------
* ONE pooled model for all places, trained on daily means: features = recent levels (lags / means), the horizon,
  time of year, signed distance to each festival, stubble-season flag, the place's long-run level.
* Target = log change versus the recent 3-day mean, so the model learns *relative* effects (e.g. "Diwali night is
  ~x1.8 of a normal day") that transfer across cities with very different baselines.
* A squared-error model gives the central estimate; two quantile models give an 80% interval (check its real coverage
  in `backtest()` - it is likely too narrow on festival days).
* It is always compared with naive baselines (persistence, 7-day mean) in `backtest()`. If it does not beat them on
  REAL data, do not ship it. Weather (wind, boundary-layer height) is NOT used yet - it is the biggest missing input.
* Training history: ground-station days where available, otherwise model (CAMS) days. CAMS does not model
  firecracker emissions well, so Diwali effects learned from model-only history will be understated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from ..data.festivals import festival_features

HORIZONS = (1, 2, 3, 4, 5)
MIN_HISTORY_DAYS = 30
FEATURES = ["h", "lag0", "mean3_log", "mean7_log", "mean30_log", "trend3_7", "level_log", "lat",
            "doy_sin", "doy_cos", "dow", "d_diwali", "d_dussehra", "d_holi", "d_newyear", "stubble"]
FEST_KEYS = ["d_diwali", "d_dussehra", "d_holi", "d_newyear", "stubble"]

_fest_cache: Dict[date, Dict[str, float]] = {}


def _fest(day: date) -> Dict[str, float]:
    if day not in _fest_cache:
        _fest_cache[day] = festival_features(day)
    return _fest_cache[day]


def _origin_table(s: pd.Series) -> pd.DataFrame:
    """Per origin day: the observed value and rolling means. Origins need an observed day + enough recent history."""
    s = s.asfreq("D")
    f = pd.DataFrame({
        "raw_lag0": s,
        "raw_m3": s.rolling(3, min_periods=2).mean(),
        "raw_m7": s.rolling(7, min_periods=4).mean(),
        "raw_m30": s.rolling(30, min_periods=15).mean(),
        "raw_level": s.rolling(365, min_periods=MIN_HISTORY_DAYS).mean(),
    })
    return f.dropna()


def _features(origins: pd.DataFrame, h, targets: pd.DatetimeIndex, lat: float) -> pd.DataFrame:
    log = lambda c: np.log1p(np.maximum(origins[c].to_numpy(), 0))
    doy = targets.dayofyear.to_numpy()
    fest = pd.DataFrame([_fest(d.date()) for d in targets], index=origins.index)
    out = pd.DataFrame({
        "h": h, "lag0": log("raw_lag0"), "mean3_log": log("raw_m3"), "mean7_log": log("raw_m7"),
        "mean30_log": log("raw_m30"), "level_log": log("raw_level"), "lat": lat,
        "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
        "dow": targets.dayofweek.to_numpy(),
    }, index=origins.index)
    out["trend3_7"] = out["mean3_log"] - out["mean7_log"]
    out = pd.concat([out, fest[FEST_KEYS]], axis=1)
    out["_base"] = out["mean3_log"]
    out["persist"], out["mean7"] = origins["raw_lag0"].to_numpy(), origins["raw_m7"].to_numpy()
    return out


def build_training_frame(series_by_place: Dict[str, pd.Series], lats: Dict[str, float]) -> pd.DataFrame:
    """One row per (place, origin day, horizon) whose outcome is known."""
    parts = []
    for place, s in series_by_place.items():
        s = s.sort_index().asfreq("D")
        origins = _origin_table(s)
        if origins.empty:
            continue
        for h in HORIZONS:
            targets = origins.index + pd.Timedelta(days=h)
            y = s.reindex(targets).to_numpy()
            keep = ~np.isnan(y)
            if not keep.any():
                continue
            o = origins[keep]
            f = _features(o, h, targets[keep], lats.get(place, 22.0))
            f["place"], f["origin"], f["target"], f["y"] = place, o.index, targets[keep], y[keep]
            f["delta"] = np.log1p(np.maximum(f["y"], 0)) - f["_base"]
            parts.append(f)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


@dataclass
class FestivalModel:
    median: HistGradientBoostingRegressor
    lower: HistGradientBoostingRegressor
    upper: HistGradientBoostingRegressor

    @classmethod
    def fit(cls, frame: pd.DataFrame) -> "FestivalModel":
        if len(frame) < 400:
            raise ValueError(f"Not enough history to train ({len(frame)} samples, need >= 400). Run the backfill first.")
        X, y = frame[FEATURES], frame["delta"]

        # Central estimate: squared error in log space (a median/absolute-error loss ignores rare festival spikes -
        # found the hard way: it predicted +9% on a day that really was x2.6). Bounds: quantile models.
        central = HistGradientBoostingRegressor(loss="squared_error", max_iter=300, learning_rate=0.06, max_depth=5,
                                                min_samples_leaf=10, random_state=0).fit(X, y)

        def bound(q):
            return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=250, learning_rate=0.05,
                                                 max_depth=4, min_samples_leaf=10, random_state=0).fit(X, y)
        return cls(central, bound(0.1), bound(0.9))

    def predict_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        base = frame["_base"].to_numpy()
        X = frame[FEATURES]
        med = self.median.predict(X)
        lo, hi = np.minimum(self.lower.predict(X), med), np.maximum(self.upper.predict(X), med)
        out = frame.copy()
        out["yhat"] = np.expm1(base + med)
        out["yhat_lower"] = np.expm1(base + lo)
        out["yhat_upper"] = np.expm1(base + hi)
        return out


def backtest(frame: pd.DataFrame, test_from: pd.Timestamp) -> Dict[str, object]:
    """Train before `test_from`, test on origins at/after it. Compare with naive baselines, overall and near festivals."""
    train = frame[(frame["origin"] < test_from) & (frame["target"] < test_from)]  # no leakage
    test = frame[frame["origin"] >= test_from]
    model = FestivalModel.fit(train)
    pred = model.predict_frame(test)

    def mae(a, b):
        m = ~(np.isnan(a) | np.isnan(b))
        return float(np.mean(np.abs(a[m] - b[m]))) if m.any() else None

    near = (pred[["d_diwali", "d_holi", "d_dussehra", "d_newyear"]].abs() <= 2).any(axis=1).to_numpy()
    res: Dict[str, object] = {"n_train": int(len(train)), "n_test": int(len(pred))}
    for name, mask in (("all", np.ones(len(pred), bool)), ("festival_days", near)):
        p = pred[mask]
        res[name] = {
            "n": int(len(p)),
            "mae_model": mae(p["y"].to_numpy(), p["yhat"].to_numpy()),
            "mae_persistence": mae(p["y"].to_numpy(), p["persist"].to_numpy()),
            "mae_mean7": mae(p["y"].to_numpy(), p["mean7"].to_numpy()),
            "interval80_coverage": float(np.mean((p["y"] >= p["yhat_lower"]) & (p["y"] <= p["yhat_upper"]))) if len(p) else None,
        }
    return res


def forecast_place(model: FestivalModel, series: pd.Series, lat: float, origin: pd.Timestamp) -> List[dict]:
    """Next 5 days after `origin` (the last complete day). Uses the latest observed day if it is at most 1 day older."""
    origins = _origin_table(series)
    origins = origins[origins.index <= origin]
    if origins.empty:
        return []
    last = origins.index[-1]
    gap = (origin - last).days
    if gap > 1:
        return []
    row = origins.iloc[[-1]]
    rows = []
    for k in HORIZONS:
        h_eff = k + gap  # a 1-day-old observation means every target is one step further out
        target = origin + pd.Timedelta(days=k)
        f = _features(row, h_eff, pd.DatetimeIndex([target]), lat)
        f["target"] = target
        rows.append(f)
    pred = model.predict_frame(pd.concat(rows))
    return [{"day": r["target"].date(), "h": k, "yhat": float(r["yhat"]), "yhat_lower": float(r["yhat_lower"]),
             "yhat_upper": float(r["yhat_upper"])} for k, (_, r) in zip(HORIZONS, pred.iterrows())]
