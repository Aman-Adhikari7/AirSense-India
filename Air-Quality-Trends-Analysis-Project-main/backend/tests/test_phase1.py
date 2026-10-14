import os

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Measurement, Place


# ---------------- auth ----------------
def test_signup_login_me_logout(client):
    r = client.post("/auth/signup", json={"email": "Asha@Example.com", "password": "correct-horse-1"})
    assert r.status_code == 201 and r.json()["email"] == "asha@example.com"
    assert "plan" not in r.json()
    assert client.get("/auth/me").json()["email"] == "asha@example.com"
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


def test_wrong_password_is_401_not_500(client):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "correct-horse-1"})
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "nope-nope-nope"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ghost@b.com", "password": "whatever-1"}).status_code == 401
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "correct-horse-1"}).status_code == 200


def test_duplicate_email_and_weak_password(client):
    body = {"email": "a@b.com", "password": "correct-horse-1"}
    assert client.post("/auth/signup", json=body).status_code == 201
    assert client.post("/auth/signup", json={**body, "email": "A@B.com"}).status_code == 400
    assert client.post("/auth/signup", json={"email": "c@d.com", "password": "short"}).status_code == 422


# ---------------- access control ----------------
@pytest.mark.parametrize("method,path,body", [
    ("post", "/scrape", {"city": "Delhi", "days": 3}),
    ("post", "/compare", {"cities": ["Delhi"], "days": 3}),
    ("post", "/forecast", {"city": "Delhi"}),
    ("post", "/forecast/train", {"city": "Delhi"}),
    ("get", "/forecast/backtest?city=Delhi", None),
    ("post", "/forecast/multi", {"cities": ["Delhi"]}),
    ("post", "/report/generate", {"report_type": "forecast", "cities": [], "charts": {}}),
    ("post", "/llm-forecast-note", {}),
])
def test_data_endpoints_require_login(client, method, path, body):
    r = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert r.status_code == 401


def test_x_plan_header_grants_nothing(client):
    r = client.post("/scrape", json={"city": "Delhi", "days": 90}, headers={"X-PLAN": "enterprise"})
    assert r.status_code == 401


def test_agent_not_mounted_when_disabled(logged_in):
    assert logged_in.get("/agent/mcp/tools/list").status_code == 404


def test_input_validation(logged_in):
    assert logged_in.post("/scrape", json={"city": "Delhi", "days": 91}).status_code == 422
    assert logged_in.post("/scrape", json={"city": "  ", "days": 3}).status_code == 422
    assert logged_in.post("/compare", json={"cities": [f"c{i}" for i in range(11)], "days": 3}).status_code == 422
    assert logged_in.post("/compare", json={"cities": [], "days": 3}).status_code == 422


# ---------------- data layer ----------------
def test_scrape_is_idempotent_utc_and_uses_catalogue(logged_in, fake_upstream):
    for _ in range(2):
        r = logged_in.post("/scrape", json={"city": "Delhi", "days": 14})
        assert r.status_code == 200, r.text
    with SessionLocal() as db:
        n = db.execute(select(func.count()).select_from(Measurement)).scalar()
        n_distinct = db.execute(select(func.count(func.distinct(Measurement.ts)))).scalar()
        assert n == n_distinct > 300, "second scrape must update, not duplicate"
        assert db.execute(select(Measurement.source).distinct()).scalars().all() == ["aggregated"]
        assert db.execute(select(Measurement.basis).distinct()).scalars().all() == ["model"]
        delhi = db.execute(select(Place).where(Place.name == "Delhi")).scalar_one()
        assert delhi.state == "Delhi"
        assert db.execute(select(Measurement.place_id)).scalars().first() == delhi.id


def test_compare_returns_kpis(logged_in, fake_upstream):
    r = logged_in.post("/compare", json={"cities": ["Delhi"], "days": 7})
    assert r.status_code == 200
    kpi = r.json()["byCity"]["Delhi"]
    assert kpi["n_points"] > 100 and 50 < kpi["mean_pm25"] < 110
    assert r.json()["best"] == r.json()["worst"] == "Delhi"


def test_non_catalogue_place_is_404_and_not_created(logged_in):
    n_before = None
    with SessionLocal() as db:
        n_before = db.execute(select(func.count()).select_from(Place)).scalar()
    for name in ("Atlantis", "Kandy"):
        assert logged_in.post("/scrape", json={"city": name, "days": 3}).status_code == 404
    with SessionLocal() as db:
        assert db.execute(select(func.count()).select_from(Place)).scalar() == n_before, "no free-text place spam"


def test_open_meteo_rows_are_hour_aligned_utc():
    from app.services.scraper import flatten_rows
    rows = flatten_rows("Delhi", 28.6, 77.2, {"hourly": {"time": ["2026-10-13T05:00"], "pm2_5": [60.0], "pm10": [120.0]}})
    assert rows[0]["ts"] == "2026-10-13 05:00:00" and rows[0]["source"] == "open-meteo"


# ---------------- forecasting ----------------
def test_forecast_end_to_end(logged_in, fake_upstream):
    logged_in.post("/scrape", json={"city": "Delhi", "days": 14})
    r = logged_in.post("/forecast", json={"city": "Delhi", "horizonDays": 2, "trainDays": 14, "use_cache": False})
    assert r.status_code == 200, r.text
    series = r.json()["series"]
    assert len(series) == 48 and all(p["yhat_lower"] <= p["yhat"] <= p["yhat_upper"] for p in series)


def test_forecast_without_data_is_404(logged_in):
    assert logged_in.post("/forecast", json={"city": "Nowhere"}).status_code == 404


def test_model_path_cannot_escape_models_dir():
    from app.services.forecast import MODELS_DIR, _model_path
    for evil in ["../../etc/passwd", "..\\..\\x", "/abs/path", "a/../../b"]:
        p = os.path.abspath(_model_path(evil))
        assert p.startswith(MODELS_DIR + os.sep), evil


# ---------------- health ----------------
def test_health(client):
    assert client.get("/simple").json() == {"status": "ok"}
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["db"]["ok"] is True and "upstream" not in r.json()


def test_production_refuses_unsafe_config(monkeypatch):
    from app.core.config import Settings
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings().validate()
