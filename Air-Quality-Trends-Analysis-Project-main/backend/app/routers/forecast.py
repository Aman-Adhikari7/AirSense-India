from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.security import require_user
from ..db import get_db
from ..schemas import CityName, ForecastIn, ForecastMultiIn
from ..services.forecast import backtest_roll, fit_and_save_model, forecast_cities, forecast_city

router = APIRouter(dependencies=[Depends(require_user)])


def _no_data_guard(fn, *args):
    try:
        return fn(*args)
    except ValueError as e:  # "No data found ... Run /scrape first."
        raise HTTPException(404, str(e))


@router.post("/forecast")
def forecast(payload: ForecastIn, db: Session = Depends(get_db)):
    result = _no_data_guard(forecast_city, db, payload.city, payload.horizonDays, payload.trainDays, payload.use_cache)
    return {"ok": True, **result}


@router.post("/forecast/train")
def forecast_train(payload: ForecastIn, db: Session = Depends(get_db)):
    path = _no_data_guard(fit_and_save_model, db, payload.city, payload.trainDays)
    return {"ok": True, "modelPath": path.rsplit("/", 1)[-1]}  # do not leak server paths


@router.get("/forecast/backtest")
def forecast_backtest(
    city: CityName,
    days: int = Query(30, ge=8, le=120),
    horizonHours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    stats = _no_data_guard(backtest_roll, db, city, days, horizonHours)
    return {"ok": True, **stats}


@router.post("/forecast/multi")
def forecast_multi(payload: ForecastMultiIn, db: Session = Depends(get_db)):
    out = forecast_cities(db, payload.cities, payload.horizonDays, payload.trainDays, payload.use_cache)
    return {"ok": True, **out, "horizonDays": payload.horizonDays}
