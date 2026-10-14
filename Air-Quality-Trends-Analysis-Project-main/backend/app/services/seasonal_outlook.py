"""Extended seasonal outlook (Days 6-30) based on historical day-of-year averages.

Design:
-------
* For horizons 6..30, chaotic short-term weather fluctuations make point forecasts unreliable.
* Instead, this service estimates typical baseline conditions using historical daily PM2.5
  observations within a +/-15 day calendar window around the target day-of-year (DOY).
* Provides the historical median (central estimate) and interquartile range (25th to 75th percentile).
"""
from __future__ import annotations

from datetime import date
from typing import List, Sequence

import numpy as np
import pandas as pd

DEFAULT_HORIZONS: Sequence[int] = range(6, 31)
MIN_HISTORICAL_SAMPLES = 10


def seasonal_forecast(
    series: pd.Series,
    origin: pd.Timestamp,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    window_days: int = 15,
) -> List[dict]:
    """
    Computes DOY-windowed historical medians and quartiles for horizons 6..30.
    
    `series`: Daily PM2.5 series with pd.DatetimeIndex.
    `origin`: Last complete day (pd.Timestamp).
    Returns list of dicts with keys: day, h, yhat, yhat_lower, yhat_upper.
    """
    # Only use observations strictly on or before origin
    hist = series[series.index <= origin].dropna()
    if len(hist) < MIN_HISTORICAL_SAMPLES:
        return []

    hist_doys = hist.index.dayofyear.to_numpy()
    hist_vals = hist.to_numpy(dtype=float)

    results: List[dict] = []
    for h in horizons:
        target = origin + pd.Timedelta(days=h)
        target_doy = target.dayofyear

        # Circular distance in day-of-year (accounts for leap years / year boundaries)
        diff = np.abs(hist_doys - target_doy)
        circ_dist = np.minimum(diff, 365 - diff)

        window_vals = hist_vals[circ_dist <= window_days]
        if len(window_vals) < MIN_HISTORICAL_SAMPLES:
            continue

        yhat = float(np.nanmedian(window_vals))
        yhat_lower = float(np.nanpercentile(window_vals, 25))
        yhat_upper = float(np.nanpercentile(window_vals, 75))

        results.append({
            "day": target.date(),
            "h": h,
            "yhat": max(0.0, yhat),
            "yhat_lower": max(0.0, yhat_lower),
            "yhat_upper": max(0.0, yhat_upper),
        })

    return results
