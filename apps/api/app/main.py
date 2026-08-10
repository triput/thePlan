from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, epics, labels, projects, quick_add, sections, tasks
from app.api.errors import register_exception_handlers
from app.bootstrap import ensure_bootstrap_user
from app.config import get_settings
from app.db import SessionLocal


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = SessionLocal()
    try:
        ensure_bootstrap_user(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="thePlan API", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)

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
    api_router.include_router(labels.router)
    api_router.include_router(sections.router)
    api_router.include_router(quick_add.router)
    app.include_router(api_router)
    return app


app = create_app()
