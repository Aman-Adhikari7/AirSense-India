import os
import tempfile

# Must be set BEFORE the app is imported (settings are read at import time).
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123456"
os.environ["APP_ENV"] = "development"
os.environ.pop("AGENT_ENABLED", None)

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, engine, init_db  # noqa: E402
from app.services.places import seed_places  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    with SessionLocal() as db:
        seed_places(db)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def logged_in(client):
    r = client.post("/auth/signup", json={"email": "Asha@Example.com", "password": "correct-horse-1"})
    assert r.status_code == 201
    return client


def fake_hours(days: int):
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    return [(end - timedelta(hours=h)) for h in range(days * 24, -1, -1)]


class _Resp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


@pytest.fixture()
def fake_upstream(monkeypatch):
    """Replace Open-Meteo + geocoding HTTP calls with deterministic fakes."""
    import math
    calls = {"air": 0, "geo": 0}

    def fake_get(url, params=None, **kw):
        if "air-quality" in url:
            calls["air"] += 1
            assert params["timezone"] == "GMT", "all sources must be requested in UTC"
            hours = fake_hours(14)
            return _Resp({"hourly": {
                "time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
                "pm2_5": [80 + 30 * math.sin(i / 24 * 2 * math.pi) for i in range(len(hours))],
                "pm10": [150 + 40 * math.sin(i / 24 * 2 * math.pi) for i in range(len(hours))],
            }})
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("requests.get", fake_get)
    return calls
