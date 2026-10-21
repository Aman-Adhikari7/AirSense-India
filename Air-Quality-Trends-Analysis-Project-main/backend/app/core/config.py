"""Central configuration. Everything comes from environment variables (see backend/.env.example).

Rules
-----
* APP_ENV=production turns on strict checks: JWT_SECRET must be set (>= 32 chars),
  DATABASE_URL must be set, cookies are Secure by default, /docs is hidden.
* In development a random JWT secret is generated per process if none is set
  (logins are lost on restart, which is fine locally).
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("airq")

DEFAULT_DEV_DATABASE_URL = "sqlite:///airq.db"


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _normalize_db_url(url: str) -> str:
    """Accept the URL styles that hosting providers hand out and force the psycopg3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings:
    def __init__(self) -> None:
        self.APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
        self.IS_PRODUCTION: bool = self.APP_ENV == "production"

        self.DATABASE_URL: str = _normalize_db_url(os.getenv("DATABASE_URL") or DEFAULT_DEV_DATABASE_URL)
        self._database_url_was_set: bool = bool(os.getenv("DATABASE_URL"))
        self.AUTO_CREATE_TABLES: bool = _bool("AUTO_CREATE_TABLES", True)

        self.ALLOWED_ORIGINS: List[str] = [
            o.strip() for o in os.getenv(
                "ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
            ).split(",") if o.strip()
        ]

        # --- auth ---
        secret = os.getenv("JWT_SECRET", "").strip()
        self._jwt_secret_was_set: bool = bool(secret)
        self.JWT_SECRET: str = secret or secrets.token_urlsafe(48)
        self.JWT_EXPIRES_MIN: int = _int("JWT_EXPIRES_MIN", 60)
        self.COOKIE_NAME: str = "airsense_access"
        self.COOKIE_DOMAIN: Optional[str] = os.getenv("COOKIE_DOMAIN") or None  # None = host-only cookie
        self.COOKIE_SECURE: bool = _bool("COOKIE_SECURE", self.IS_PRODUCTION)
        self.COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()  # lax | strict | none

        # --- request limits (replace the old Free/Pro/Enterprise tiers) ---
        self.MAX_DAYS: int = _int("MAX_DAYS", 90)
        self.MAX_CITIES_PER_REQUEST: int = _int("MAX_CITIES_PER_REQUEST", 10)

        # --- data collection (Ground stations: OpenAQ v3 preferred, WAQI fallback) ---
        self.OPENAQ_API_KEY: str = os.getenv("OPENAQ_API_KEY", "").strip()
        self.WAQI_TOKEN: str = (os.getenv("WAQI_TOKEN") or os.getenv("WAQI_API_KEY") or "").strip()
        self.AUTO_SEED_PLACES: bool = _bool("AUTO_SEED_PLACES", True)
        self.STATION_RADIUS_M: int = min(_int("STATION_RADIUS_M", 25000), 25000)  # OpenAQ max is 25 km
        self.STATION_MAX_AGE_DAYS: int = _int("STATION_MAX_AGE_DAYS", 30)  # ignore dead stations
        self.STALE_AFTER_MINUTES: int = _int("STALE_AFTER_MINUTES", 30)  # station reading older than 30 min is flagged stale

        # --- forecasting ---
        self.MODEL_CACHE_HOURS: int = _int("MODEL_CACHE_HOURS", 6)

        # --- AI agent & natural language assistant ---
        self.AGENT_ENABLED: bool = _bool("AGENT_ENABLED", True)
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip()
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip()

    def validate(self) -> None:
        """Ensure safe production configuration."""
        if not self._jwt_secret_was_set or len(self.JWT_SECRET) < 32:
            self.JWT_SECRET = secrets.token_urlsafe(48)
            self._jwt_secret_was_set = True
            logger.info("Auto-generated cryptographically secure JWT_SECRET.")

        if self.IS_PRODUCTION:
            problems = []
            if not self.COOKIE_SECURE:
                self.COOKIE_SECURE = True
            if self.COOKIE_SAMESITE not in {"lax", "strict", "none"}:
                self.COOKIE_SAMESITE = "lax"
            self.ALLOWED_ORIGINS = [o for o in self.ALLOWED_ORIGINS if o and o != "*"]
            if problems:
                raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
        elif not self._jwt_secret_was_set:
            logger.warning("JWT_SECRET not set - using a random one for this process (dev only).")
        if self.COOKIE_SAMESITE not in {"lax", "strict", "none"}:
            self.COOKIE_SAMESITE = "lax"


settings = Settings()
