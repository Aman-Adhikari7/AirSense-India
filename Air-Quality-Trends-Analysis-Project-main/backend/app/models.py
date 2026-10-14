"""Database schema.

Conventions
-----------
* Every DateTime column stores NAIVE UTC. Convert to IST (Asia/Kolkata) only for display.
* `measurements.city` is the place name used by the current API; `place_id` links to `places`
  once the Phase 2 India places catalogue is loaded.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
    """Naive UTC 'now' (datetime.utcnow() is deprecated)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(190), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)


class Place(Base):
    """A place in India we can fetch data for (state capital, city, district...)."""
    __tablename__ = "places"
    __table_args__ = (UniqueConstraint("name", "state", name="uq_place_name_state"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, index=True)
    state = Column(String(80), nullable=True, index=True)
    district = Column(String(120), nullable=True)
    kind = Column(String(20), nullable=False, default="city")  # state_capital | city | district
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Nearest ground monitoring station (OpenAQ v3 location), discovered by the collector job.
    station_id = Column(Integer, nullable=True)
    station_name = Column(String(160), nullable=True)
    station_distance_km = Column(Float, nullable=True)
    pm25_sensor_id = Column(Integer, nullable=True)
    pm10_sensor_id = Column(Integer, nullable=True)
    station_checked_at = Column(DateTime, nullable=True)

    measurements = relationship("Measurement", back_populates="place")


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("ts", "city", "source", name="uq_measurement_ts_city_source"),
        Index("ix_measurements_city_source_ts", "city", "source", "ts"),
    )

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, nullable=False)  # naive UTC, hour-aligned
    city = Column(String(120), nullable=False)
    place_id = Column(Integer, ForeignKey("places.id", ondelete="SET NULL"), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    pm25 = Column(Float, nullable=True)
    pm10 = Column(Float, nullable=True)
    source = Column(String(32), nullable=False)  # 'aggregated' for what the app reads
    basis = Column(String(8), nullable=True)  # 'ground' (monitoring station) | 'model' (Open-Meteo/CAMS estimate)

    place = relationship("Place", back_populates="measurements")


class DailyMeasurement(Base):
    """Daily means per place (day = calendar day in IST). Long retention, used to train the forecast model."""
    __tablename__ = "daily_measurements"
    __table_args__ = (
        UniqueConstraint("city", "day", name="uq_daily_city_day"),
        Index("ix_daily_city_day", "city", "day"),
    )

    id = Column(Integer, primary_key=True)
    city = Column(String(120), nullable=False)
    place_id = Column(Integer, ForeignKey("places.id", ondelete="SET NULL"), nullable=True)
    day = Column(Date, nullable=False)  # IST calendar day
    pm25 = Column(Float, nullable=True)
    pm10 = Column(Float, nullable=True)
    n_hours = Column(Integer, nullable=True)  # hourly values behind the mean (null for backfilled daily values)
    basis = Column(String(8), nullable=False, default="model")  # 'ground' beats 'model' for the same day


class Forecast(Base):
    """Stored forecast points (precomputed by the nightly job `python -m app.jobs.forecast`)."""
    __tablename__ = "forecasts"
    __table_args__ = (
        Index("ix_forecasts_city_model_generated", "city", "model", "generated_at"),
    )

    id = Column(Integer, primary_key=True)
    city = Column(String(120), nullable=False)
    place_id = Column(Integer, ForeignKey("places.id", ondelete="SET NULL"), nullable=True)
    model = Column(String(32), nullable=False)  # e.g. 'sarimax', 'cams', 'seasonal-outlook'
    generated_at = Column(DateTime, default=utcnow, nullable=False)
    ts = Column(DateTime, nullable=False)  # naive UTC, the time being predicted
    yhat = Column(Float, nullable=True)
    yhat_lower = Column(Float, nullable=True)
    yhat_upper = Column(Float, nullable=True)
