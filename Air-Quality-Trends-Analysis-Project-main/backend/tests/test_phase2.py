import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import DailyMeasurement, Forecast, Measurement, Place, utcnow
from app.services import aqi
from app.services.aggregate import best_available
from app.services.places import AmbiguousPlace, PlaceNotFound, resolve_place, seed_places


# ---------------- CPCB AQI ----------------
@pytest.mark.parametrize("pollutant,conc,expected", [
    ("pm25", 0, 0), ("pm25", 30, 50), ("pm25", 60, 100), ("pm25", 90, 200), ("pm25", 120, 300),
    ("pm25", 250, 400), ("pm25", 380, 500), ("pm25", 900, 500),
    ("pm10", 50, 50), ("pm10", 100, 100), ("pm10", 250, 200), ("pm10", 350, 300), ("pm10", 430, 400),
])
def test_cpcb_breakpoints_are_exact(pollutant, conc, expected):
    assert aqi.sub_index(pollutant, conc) == expected


def test_aqi_is_monotonic_and_interpolated():
    vals = [aqi.sub_index("pm25", c / 2) for c in range(0, 800)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert aqi.sub_index("pm25", 80) == 167  # 101 + (200-101)/(90-60)*(80-60)
    assert aqi.sub_index("pm25", -1) is None and aqi.sub_index("pm25", None) is None


def test_categories_and_colours_follow_green_yellow_red():
    assert aqi.category_for(50)["key"] == "good" and aqi.category_for(51)["key"] == "satisfactory"
    assert aqi.category_for(200)["key"] == "moderate" and aqi.category_for(201)["key"] == "poor"
    assert aqi.category_for(401)["key"] == "severe" and aqi.category_for(None)["key"] == "unknown"
    assert aqi.category_for(25)["color"] == "#1E9E57"      # green
    assert aqi.category_for(150)["color"] == "#F4C20D"     # yellow
    assert aqi.category_for(350)["color"] == "#D32F2F"     # red


def test_compute_aqi_takes_worst_pollutant_and_labels_basis():
    r = aqi.compute_aqi(pm25=40, pm10=300)
    assert r["dominant"] == "pm10" and r["aqi"] == aqi.sub_index("pm10", 300)
    assert "PM-only" in r["basis"] and aqi.compute_aqi() is None


def test_24h_mean_needs_16_valid_hours():
    assert aqi.mean_24h([10.0] * 16) == 10.0
    assert aqi.mean_24h([10.0] * 15 + [None] * 9) is None


# ---------------- places catalogue ----------------
def test_catalogue_covers_every_state_and_ut(client):
    states = client.get("/places/states").json()["states"]
    assert len(states) == 36
    assert all(s["n_places"] >= 1 for s in states)
    assert {"Punjab", "Delhi", "Ladakh", "Lakshadweep", "Tamil Nadu"} <= {s["state"] for s in states}


def test_seed_is_idempotent_and_resolve_place():
    with SessionLocal() as db:
        n = db.execute(select(func.count()).select_from(Place)).scalar()
        assert seed_places(db) == 0 and db.execute(select(func.count()).select_from(Place)).scalar() == n
        assert resolve_place(db, "ludhiana").state == "Punjab"
        assert resolve_place(db, "Ludhiana, Punjab").name == "Ludhiana"
        with pytest.raises(PlaceNotFound):
            resolve_place(db, "Colombo")
        db.add(Place(name="Aurangabad", state="Bihar", kind="city", latitude=24.75, longitude=84.37))
        db.add(Place(name="Aurangabad", state="Maharashtra", kind="city", latitude=19.88, longitude=75.34))
        db.commit()
        with pytest.raises(AmbiguousPlace):
            resolve_place(db, "Aurangabad")
        assert resolve_place(db, "Aurangabad, Bihar").state == "Bihar"


def test_places_api_is_public_and_filters(client):
    r = client.get("/places", params={"state": "punjab", "q": "ludh"})
    assert r.status_code == 200 and [p["name"] for p in r.json()["places"]] == ["Ludhiana"]
    assert client.get("/about/health").status_code == 200


# ---------------- ground beats model ----------------
def _row(ts, pm25, pm10=None, source="x"):
    return {"ts": ts, "pm25": pm25, "pm10": pm10, "source": source}


def test_best_available_prefers_ground_and_never_blends():
    model = [_row("2026-10-13 01:00:00", 100, 200), _row("2026-10-13 02:00:00", 110, 210), _row("2026-10-13 03:00:00", 120, 220)]
    ground = [_row("2026-10-13 02:00:00", 40, 80), _row("2026-10-13 03:00:00", None, 90)]
    out = {r["ts"]: r for r in best_available("Delhi", 28.6, 77.2, ground, model)}
    assert out["2026-10-13 01:00:00"]["basis"] == "model" and out["2026-10-13 01:00:00"]["pm25"] == 100
    assert out["2026-10-13 02:00:00"]["basis"] == "ground" and out["2026-10-13 02:00:00"]["pm25"] == 40  # not 75
    assert out["2026-10-13 03:00:00"]["basis"] == "model", "ground row without PM2.5 must not replace the model"


# ---------------- OpenAQ v3 client (mocked HTTP) ----------------
class _R:
    def __init__(self, payload, code=200):
        self._p, self.status_code = payload, code
    def raise_for_status(self): pass
    def json(self): return self._p


@pytest.fixture()
def openaq(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "OPENAQ_API_KEY", "test-key")
    monkeypatch.setenv("OPENAQ_MIN_INTERVAL_S", "0")
    seen = []

    def fake_get(url, params=None, headers=None, **kw):
        seen.append((url, params, headers))
        assert headers == {"X-API-Key": "test-key"}
        now = datetime.utcnow()
        if url.endswith("/v3/locations"):
            assert params["parameters_id"] == 2 and params["radius"] <= 25000
            return _R({"results": [
                {"id": 1, "name": "Dead station", "coordinates": {"latitude": 28.61, "longitude": 77.21},
                 "datetimeLast": {"utc": (now - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")},
                 "sensors": [{"id": 11, "parameter": {"name": "pm25"}}]},
                {"id": 2, "name": "Far station", "coordinates": {"latitude": 28.80, "longitude": 77.21},
                 "datetimeLast": {"utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
                 "sensors": [{"id": 21, "parameter": {"name": "pm25"}}]},
                {"id": 3, "name": "Near station", "coordinates": {"latitude": 28.62, "longitude": 77.22},
                 "datetimeLast": {"utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
                 "sensors": [{"id": 31, "parameter": {"name": "pm25"}}, {"id": 32, "parameter": {"name": "pm10"}},
                             {"id": 33, "parameter": {"name": "no2"}}]},
            ]})
        if "/sensors/" in url and url.endswith("/hours"):
            sid = int(url.split("/sensors/")[1].split("/")[0])
            base = 90.0 if sid == 31 else 170.0
            hours = [(now - timedelta(hours=h)).replace(minute=0, second=0, microsecond=0) for h in range(30, -1, -1)]
            return _R({"results": [{"value": base, "period": {"datetimeFrom": {"utc": h.strftime("%Y-%m-%dT%H:%M:%SZ")}}} for h in hours]
                       + [{"value": -999, "period": {"datetimeFrom": {"utc": "2020-01-01T00:00:00Z"}}}]})
        if url.endswith("/latest"):
            return _R({"results": [{"sensorsId": 31, "value": 77.0, "datetime": {"utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")}}]})
        raise AssertionError(url)

    monkeypatch.setattr("requests.get", fake_get)
    return seen


def test_find_station_picks_nearest_active_pm25_station(openaq):
    from app.services.fetchers import openaq_v3
    st = openaq_v3.find_station(28.6139, 77.2090)
    assert st["station_id"] == 3 and st["pm25_sensor_id"] == 31 and st["pm10_sensor_id"] == 32
    assert st["distance_km"] < 5


def test_sensor_hours_drop_faulty_negative_values(openaq):
    from app.services.fetchers import openaq_v3
    now = datetime.utcnow()
    got = openaq_v3.fetch_sensor_hours(31, now - timedelta(days=2), now)
    assert len(got) == 31 and set(got.values()) == {90.0}


def test_missing_api_key_is_a_clear_error(monkeypatch):
    from app.core.config import settings
    from app.services.fetchers import openaq_v3
    monkeypatch.setattr(settings, "OPENAQ_API_KEY", "")
    with pytest.raises(openaq_v3.OpenAQError, match="OPENAQ_API_KEY"):
        openaq_v3.find_station(1, 1)


def test_collect_place_uses_ground_data_when_station_exists(openaq, monkeypatch):
    import math
    from app.services.scraper import collect_place
    from tests.conftest import _Resp, fake_hours
    orig = __import__("requests").get

    def combined(url, params=None, **kw):
        if "air-quality-api" in url:
            hours = fake_hours(3)
            return _Resp({"hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
                                     "pm2_5": [200.0] * len(hours), "pm10": [300.0] * len(hours)}})
        return orig(url, params=params, **kw)

    monkeypatch.setattr("requests.get", combined)
    with SessionLocal() as db:
        place = db.execute(select(Place).where(Place.name == "Delhi")).scalar_one()
        res = collect_place(db, place, 2)
        assert place.station_id == 3 and place.station_name == "Near station"
        assert res["ground_hours"] == 31 and 0.3 < res["ground_share"] < 0.6  # 31 ground hours inside 73 model hours
        rows = db.execute(select(Measurement.basis, Measurement.pm25).where(Measurement.ts <= utcnow())).all()
        assert ("ground", 90.0) in rows and ("model", 200.0) in rows


# ---------------- live + map ----------------
def _insert_hours(db, city, pm25, basis, hours=30, end=None):
    end = (end or utcnow()).replace(minute=0, second=0, microsecond=0)
    db.add_all([Measurement(ts=end - timedelta(hours=h), city=city, source="aggregated", pm25=pm25, pm10=pm25 * 1.8, basis=basis)
                for h in range(hours)])
    db.commit()


def test_live_endpoint_reports_aqi_basis_and_freshness(client):
    with SessionLocal() as db:
        delhi = db.execute(select(Place).where(Place.name == "Delhi")).scalar_one()
        delhi.station_id, delhi.station_name, delhi.station_distance_km = 3, "Anand Vihar, Delhi - DPCC", 2.4
        db.commit()
        _insert_hours(db, "Delhi", 80.0, "ground")
        pid = delhi.id
    r = client.get(f"/places/{pid}/live").json()
    assert r["aqi"]["aqi"] == max(167, aqi.sub_index("pm10", 144)) and r["aqi"]["key"] in ("moderate",)
    assert r["latest"]["basis"] == "ground" and r["latest"]["stale"] is False
    assert r["source"].startswith("Ground station: Anand Vihar") and r["ground_share_24h"] == 1.0


def test_live_flags_stale_and_missing_data(client):
    with SessionLocal() as db:
        _insert_hours(db, "Mumbai", 30.0, "model", hours=30, end=utcnow() - timedelta(hours=10))
        mumbai = db.execute(select(Place).where(Place.name == "Mumbai")).scalar_one().id
        kolkata = db.execute(select(Place).where(Place.name == "Kolkata")).scalar_one().id
    old = client.get(f"/places/{mumbai}/live").json()
    assert old["latest"]["stale"] is True and "no active monitoring station" in old["source"]
    none = client.get(f"/places/{kolkata}/live").json()
    assert none["aqi"] is None and none["latest"] is None and "fewer than 16" in none["aqi_reason"]
    assert client.get("/places/999999/live").status_code == 404


def test_map_summary_colours_states(client):
    with SessionLocal() as db:
        _insert_hours(db, "Delhi", 200.0, "ground")   # very poor / severe range
        _insert_hours(db, "Chennai", 20.0, "model")   # good
    m = client.get("/map/summary").json()
    states = {s["state"]: s for s in m["states"]}
    assert len(states) == 36
    assert states["Delhi"]["key"] in ("very_poor", "severe") and states["Delhi"]["color"] in ("#D32F2F", "#7B1113")
    assert states["Tamil Nadu"]["key"] == "good" and states["Tamil Nadu"]["color"] == "#1E9E57"
    assert states["Ladakh"]["aqi"] is None and states["Ladakh"]["key"] == "unknown"
    delhi = next(p for p in m["places"] if p["name"] == "Delhi")
    assert delhi["basis"] == "ground" and delhi["lat"] and delhi["aqi"] > 300


# ---------------- health info ----------------
def test_health_effects_cover_low_medium_high(client):
    h = client.get("/about/health").json()
    assert set(h["groups"]) == {"low", "medium", "high"}
    keys = [c["key"] for c in h["categories"]]
    assert keys == ["good", "satisfactory", "moderate", "poor", "very_poor", "severe"]
    assert all(c["color"].startswith("#") and c["what_to_do"] for c in h["categories"])
    assert h["reference_values"]["who_2021"]["pm25_24h"] == 15 and h["reference_values"]["india_naaqs"]["pm25_24h"] == 60
    assert "not medical advice" in h["disclaimer"]


# ---------------- festivals ----------------
def test_festival_features_and_upcoming():
    from app.data.festivals import festival_features, upcoming
    f = festival_features(date(2026, 11, 8))
    assert f["d_diwali"] == 0 and f["stubble"] == 1
    assert festival_features(date(2026, 11, 6))["d_diwali"] == 2   # Dhanteras: Diwali is 2 days ahead
    assert festival_features(date(2026, 7, 1))["d_diwali"] == 10 and festival_features(date(2026, 7, 1))["stubble"] == 0
    up = upcoming(date(2026, 10, 13), 30)
    assert {"festival": "diwali", "date": "2026-11-08", "in_days": 26} in up


# ---------------- festival model ----------------
def _synthetic_series(seed, base, start="2022-09-01", end="2025-12-31"):
    from app.data.festivals import FESTIVALS
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    doy = days.dayofyear.to_numpy()
    level = base * (1 + 0.6 * np.cos(2 * np.pi * (doy - 355) / 365))          # winter peak
    noise = np.exp(np.cumsum(rng.normal(0, 0.08, len(days))) * 0.15 + rng.normal(0, 0.12, len(days)))
    mult = np.ones(len(days))
    for d in FESTIVALS["diwali"]:
        for off, m in ((0, 2.6), (1, 1.7)):
            idx = (pd.Timestamp(d) + pd.Timedelta(days=off) - days[0]).days
            if 0 <= idx < len(days):
                mult[idx] = m
    return pd.Series(level * noise * mult, index=days)


@pytest.fixture(scope="module")
def synth():
    return {f"P{i}": _synthetic_series(i, 60 + 25 * i) for i in range(5)}


def test_model_learns_diwali_uplift(synth):
    from app.services.festival_model import FestivalModel, build_training_frame, forecast_place
    frame = build_training_frame(synth, {k: 25.0 for k in synth})
    assert len(frame) > 5000
    model = FestivalModel.fit(frame[frame["target"] < "2025-09-01"])      # never saw Diwali 2025
    s = synth["P2"]
    # 2025 Diwali = 20 Oct. Forecast from 17 Oct (target 18..22 Oct) vs a control window 3 weeks earlier.
    fc = forecast_place(model, s, 25.0, pd.Timestamp("2025-10-17"))
    ctl = forecast_place(model, s, 25.0, pd.Timestamp("2025-09-26"))
    by_day = {f["day"]: f["yhat"] for f in fc}
    peak, pre = by_day[date(2025, 10, 20)], by_day[date(2025, 10, 18)]
    ctl_ratio = ctl[3]["yhat"] / ctl[0]["yhat"]
    assert peak / pre > 1.5 and peak / pre > 1.4 * ctl_ratio, (peak, pre, ctl_ratio)
    assert all(f["yhat_lower"] <= f["yhat"] <= f["yhat_upper"] for f in fc) and len(fc) == 5


def test_backtest_reports_baselines_and_beats_persistence_on_festival_days(synth):
    from app.services.festival_model import backtest, build_training_frame
    frame = build_training_frame(synth, {k: 25.0 for k in synth})
    res = backtest(frame, pd.Timestamp("2025-06-01"))
    assert {"n_train", "n_test", "all", "festival_days"} <= set(res)
    fd = res["festival_days"]
    assert fd["n"] > 20 and fd["mae_model"] < fd["mae_persistence"], res
    assert res["all"]["mae_persistence"] is not None and 0 <= res["all"]["interval80_coverage"] <= 1


def test_model_refuses_to_train_on_too_little_data():
    from app.services.festival_model import FestivalModel, build_training_frame
    s = _synthetic_series(1, 80, start="2025-01-01", end="2025-03-01")
    with pytest.raises(ValueError, match="Not enough history"):
        FestivalModel.fit(build_training_frame({"X": s}, {"X": 25.0}))


def test_nightly_job_stores_forecast_and_api_serves_it(client, synth):
    from app.jobs.forecast import run
    names = ["Delhi", "Mumbai", "Chennai", "Kolkata", "Pune"]
    with SessionLocal() as db:
        for name, (_, s) in zip(names, synth.items()):
            pid = db.execute(select(Place.id).where(Place.name == name)).scalar_one()
            db.add_all([DailyMeasurement(city=name, place_id=pid, day=d.date(), pm25=float(v), basis="model")
                        for d, v in s["2024-01-01":"2025-10-17"].items()])
        db.commit()
        out = run(db, today_ist=date(2025, 10, 18))
        assert out["places"] == 5 and out["rows"] == 25 and out["skipped"] == 0
        assert run(db, today_ist=date(2025, 10, 18))["rows"] == 25   # re-run replaces, never piles up
        assert db.execute(select(func.count()).select_from(Forecast)).scalar() == 25
        pid = db.execute(select(Place.id).where(Place.name == "Delhi")).scalar_one()
    r = client.get(f"/places/{pid}/forecast")
    assert r.status_code == 200
    j = r.json()
    assert len(j["days"]) == 5 and j["days"][0]["date"] == "2025-10-18" and j["experimental"] is True
    assert all(d["aqi_low"] <= d["aqi"] <= d["aqi_high"] and d["color"].startswith("#") for d in j["days"])
    assert any(u["festival"] == "diwali" and u["in_days"] == 2 for u in j["upcoming_festivals"])
    assert client.get("/places/999999/forecast").status_code == 404


def test_forecast_job_refuses_without_history(client):
    from app.jobs.forecast import run
    with SessionLocal() as db, pytest.raises(ValueError, match="No daily history"):
        run(db)


# ---------------- daily rollup ----------------
def test_daily_rollup_uses_ist_days_and_needs_16_hours():
    from app.services.daily import daily_from_hourly, upsert_daily
    # 2026-10-12 18:30 UTC = 2026-10-13 00:00 IST -> IST day 13th starts at 18:30 UTC on the 12th
    hours = [(datetime(2026, 10, 12, 18, 30) + timedelta(hours=h), 50.0, 90.0, "ground") for h in range(24)]
    days = daily_from_hourly(hours)
    assert [d["day"] for d in days] == [date(2026, 10, 13)] and days[0]["basis"] == "ground" and days[0]["n_hours"] == 24
    assert daily_from_hourly(hours[:10]) == []
    with SessionLocal() as db:
        row = {"city": "Delhi", "place_id": None, "day": date(2026, 10, 13), "pm25": 50.0, "pm10": 90.0, "n_hours": 24, "basis": "ground"}
        assert upsert_daily(db, [row]) == 1
        assert upsert_daily(db, [{**row, "pm25": 999.0, "basis": "model"}]) == 0, "model must not overwrite ground"
        assert db.execute(select(DailyMeasurement.pm25)).scalar() == 50.0


# ---------------- jobs ----------------
def test_collect_job_stores_hourly_and_daily_and_survives_a_failing_place(fake_upstream, monkeypatch):
    from app.jobs import collect
    from app.services import scraper
    real = scraper.collect_place

    def flaky(db, place, days):
        if place.name == "Mumbai":
            raise RuntimeError("upstream boom")
        return real(db, place, days)

    monkeypatch.setattr(collect, "collect_place", flaky)
    out = collect.run(days=3, only=["Delhi", "Mumbai"])
    assert out == {"ok": 1, "failed": 1}
    with SessionLocal() as db:
        assert db.execute(select(func.count()).select_from(Measurement).where(Measurement.city == "Delhi")).scalar() > 100
        assert db.execute(select(func.count()).select_from(Measurement).where(Measurement.city == "Mumbai")).scalar() == 0
        daily = db.execute(select(DailyMeasurement).where(DailyMeasurement.city == "Delhi")).scalars().all()
        assert len(daily) >= 2 and all(d.n_hours >= 16 and d.basis == "model" for d in daily)


def test_backfill_chunks_a_multi_year_range_into_daily_rows(fake_upstream):
    from app.jobs.backfill import _chunks, backfill_place
    chunks = list(_chunks(date(2022, 8, 1), date(2026, 10, 12)))
    assert chunks[0][0] == date(2022, 8, 1) and chunks[-1][1] == date(2026, 10, 12)
    assert all((b - a).days < 365 for a, b in chunks) and all(chunks[i][1] + timedelta(days=1) == chunks[i + 1][0] for i in range(len(chunks) - 1))
    with SessionLocal() as db:
        place = db.execute(select(Place).where(Place.name == "Delhi")).scalar_one()
        res = backfill_place(db, place, date(2025, 1, 1), date(2026, 10, 12))
        assert res["model_days"] > 0 and res["ground_days"] == 0   # no OpenAQ key in tests
        assert fake_upstream["air"] == 2                             # two ~yearly requests, not one per day
