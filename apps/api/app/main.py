import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import (
    auth,
    assist,
    calendar,
    epics,
    focus_windows,
    labels,
    outlines,
    plans,
    projects,
    quick_add,
    reminders,
    scheduled_blocks,
    schedule,
    search,
    sections,
    settings as settings_routes,
    tasks,
)
from app.api.errors import register_exception_handlers
from app.api.middleware import PasswordChangeGateMiddleware
from app.bootstrap import ensure_bootstrap_user
from app.config import get_settings
from app.db import SessionLocal
from app.services.demo_seed import ensure_demo_nebula

logger = logging.getLogger(__name__)


def _resolve_repo_root() -> Path:
    """Local: ThePlan/; Docker (/app/app/main.py): /app."""
    api_root = Path(__file__).resolve().parents[1]
    if api_root.parent.name == "apps":
        return api_root.parents[1]
    return api_root


_REPO_ROOT = _resolve_repo_root()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    db = SessionLocal()
    try:
        ensure_bootstrap_user(db)
        if settings.seed_demo_user:
            ensure_demo_nebula(
                db,
                repo_root=_REPO_ROOT,
                configured_password=settings.demo_nebula_password,
            )
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="thePlan API", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)

    app.add_middleware(PasswordChangeGateMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.session_https_only,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(auth.router)
    api_router.include_router(epics.router)
    api_router.include_router(projects.router)
    api_router.include_router(tasks.router)
    api_router.include_router(reminders.router)
    api_router.include_router(labels.router)
    api_router.include_router(focus_windows.router)
    api_router.include_router(plans.router)
    api_router.include_router(sections.router)
    api_router.include_router(quick_add.router)
    api_router.include_router(assist.router)
    api_router.include_router(outlines.router)
    api_router.include_router(scheduled_blocks.router)
    api_router.include_router(schedule.router)
    api_router.include_router(calendar.router)
    api_router.include_router(search.router)
    api_router.include_router(settings_routes.router)
    app.include_router(api_router)
    _maybe_mount_web(app)
    return app


def _maybe_mount_web(app: FastAPI) -> None:
    """Serve apps/web dist when THEPLAN_WEB_DIST is set (desktop sidecar same-origin UI)."""
    raw = os.environ.get("THEPLAN_WEB_DIST", "").strip()
    if not raw:
        return
    dist = Path(raw)
    if not dist.is_dir() or not (dist / "index.html").is_file():
        logger.warning("THEPLAN_WEB_DIST is set but unusable: %s", dist)
        return
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
    logger.info("Serving web UI from %s", dist)


app = create_app()
