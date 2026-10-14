from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.security import require_user
from ..db import get_db
from ..schemas import CityWindowIn, CompareIn
from ..services.scraper import ensure_window_for_city, ensure_window_for_city_with_counts
from ..utils.compare import compare_logic

# Every route here needs a logged-in user (replaces the old plan checks).
router = APIRouter(dependencies=[Depends(require_user)])


def _upstream_guard(fn, *args):
    """Turn catalogue/upstream failures into a clean 502/404 instead of a stack trace."""
    try:
        return fn(*args)
    except RuntimeError as e:
        msg = str(e)
        if msg.startswith("PlaceNotFound"):
            raise HTTPException(404, msg.split(": ", 1)[-1])
        if msg.startswith("AmbiguousPlace"):
            raise HTTPException(400, msg.split(": ", 1)[-1])
        raise HTTPException(502, "Upstream data provider failed. Please try again shortly.")


@router.post("/scrape")
def scrape_city(payload: CityWindowIn, db: Session = Depends(get_db)):
    inserted, (lat, lon) = _upstream_guard(ensure_window_for_city, db, payload.city, payload.days, payload.sources)
    return {"ok": True, "city": payload.city, "inserted": inserted, "lat": lat, "lon": lon}


@router.post("/compare")
def compare_cities(payload: CompareIn, db: Session = Depends(get_db)):
    for c in payload.cities:
        _upstream_guard(ensure_window_for_city, db, c, payload.days, None)
    return {"ok": True, **compare_logic(db, payload.cities, payload.days)}


@router.post("/scrape/aggregate")
def scrape_city_aggregate(payload: CityWindowIn, db: Session = Depends(get_db)):
    counts, (lat, lon) = _upstream_guard(
        ensure_window_for_city_with_counts, db, payload.city, payload.days, payload.sources
    )
    return {
        "ok": True,
        "city": payload.city,
        "lat": lat,
        "lon": lon,
        "inserted": sum(counts.values()),
        "counts": counts,
        "aggregated": counts.get("aggregated", 0),
    }
