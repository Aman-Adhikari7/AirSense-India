import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.logging_mw import log_requests
from .core.rate_limit import rate_limit_middleware
from .db import SessionLocal, init_db
from .services.places import seed_if_empty
from .routers.auth import router as auth_router
from .routers.compare import router as compare_router
from .routers.forecast import router as forecast_router
from .routers.health import router as health_router
from .routers.places import router as places_router
from .routers.report import router as report_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("airq")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()  # refuses to start with unsafe production settings
    if settings.AUTO_CREATE_TABLES:
        init_db()
        if settings.AUTO_SEED_PLACES:
            with SessionLocal() as db:
                seed_if_empty(db)
    logger.info("AirSense India API started (env=%s, agent=%s)", settings.APP_ENV, settings.AGENT_ENABLED)
    yield


app = FastAPI(
    title="AirSense India API",
    lifespan=lifespan,
    docs_url=None if settings.IS_PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if settings.IS_PRODUCTION else "/openapi.json",
)

app.middleware("http")(rate_limit_middleware(requests_per_minute=120))
app.middleware("http")(log_requests)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["health"])
app.include_router(places_router, tags=["places"])  # public, read-only
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(compare_router, tags=["data"])
app.include_router(forecast_router, tags=["forecast"])
app.include_router(report_router, tags=["report"])

if settings.AGENT_ENABLED:  # AI natural language assistant and planning agent
    from .routers.agent import public_router as agent_public_router, router as agent_router
    app.include_router(agent_public_router, prefix="/agent", tags=["agent"])
    app.include_router(agent_router, prefix="/agent", tags=["agent"])

# Serve built frontend for single-port convenience (e.g. on :8000 or production deployment)
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        target = os.path.join(frontend_dist, full_path)
        if full_path and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(frontend_dist, "index.html"))

