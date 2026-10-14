import requests
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db import get_db

router = APIRouter()


@router.get("/simple")
def simple_health():
    """Liveness probe: no database, no network."""
    return {"status": "ok"}


@router.get("/healthz")
def healthz(deep: bool = Query(False, description="Also probe the Open-Meteo upstream"), db: Session = Depends(get_db)):
    """Readiness probe. 503 when the database is unreachable. Upstream is only probed with ?deep=true."""
    db_ok = True
    try:
        db.execute(text("SELECT 1")).scalar()
    except Exception:
        db_ok = False

    body = {"status": "ok" if db_ok else "degraded", "db": {"ok": db_ok}}

    if deep:
        try:
            r = requests.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={"latitude": 28.61, "longitude": 77.21, "hourly": "pm2_5", "forecast_days": 1},
                timeout=5,
            )
            body["upstream"] = {"ok": r.status_code < 500}
        except Exception:
            body["upstream"] = {"ok": False}

    return JSONResponse(body, status_code=200 if db_ok else 503)
