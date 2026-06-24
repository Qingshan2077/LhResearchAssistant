"""Research Assistant Backend — FastAPI entry point."""

import argparse
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import inspect

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.database.sqlite import AppSetting
from app.logs import setup_logging
from app.services.crypto import decrypt_api_key
from app.services.proxy import set_proxy
from app.services.semantic_scholar_api import set_semantic_scholar_api_key
from app.version import __version__


def _run_startup_migrations() -> None:
    """Apply database migrations on packaged first start.

    PyInstaller launches can have an unpredictable current working directory, so
    resolve alembic.ini from the backend package root instead of relying on CWD.
    """
    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("Alembic config not found at {}; skipping startup migrations", alembic_ini)
        return
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig

        config = AlembicConfig(str(alembic_ini))
        config.set_main_option("script_location", str(backend_root / "alembic"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.db_path}")
        alembic_command.upgrade(config, "head")
        logger.info("Alembic migrations are up to date")
    except Exception as exc:
        logger.exception("Alembic migration failed: {}", exc)


def _ensure_required_tables() -> None:
    """Repair half-initialized local SQLite databases created by older packaged builds."""
    required_tables = {"projects", "papers", "llm_providers", "app_settings"}
    try:
        existing_tables = set(inspect(engine).get_table_names())
    except Exception as exc:
        logger.exception("Could not inspect database schema: {}", exc)
        return

    missing_tables = required_tables - existing_tables
    if not missing_tables:
        return

    logger.warning("Database schema is missing {}; creating missing ORM tables", sorted(missing_tables))
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.exception("Could not create missing database tables: {}", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize process-wide services."""
    setup_logging()
    _run_startup_migrations()
    _ensure_required_tables()
    if inspect(engine).has_table(AppSetting.__tablename__):
        db = SessionLocal()
        try:
            proxy_enabled = db.get(AppSetting, "proxy_enabled")
            proxy_url = db.get(AppSetting, "proxy_url")
            set_proxy(
                proxy_url.value
                if proxy_enabled and proxy_enabled.value == "true" and proxy_url
                else None
            )
            s2_key = db.get(AppSetting, "semantic_scholar_api_key")
            set_semantic_scholar_api_key(
                decrypt_api_key(s2_key.value) if s2_key else ""
            )
        finally:
            db.close()
    else:
        set_proxy(None)
        set_semantic_scholar_api_key("")
    yield


app = FastAPI(
    title="Research Assistant API",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # This is a localhost-only desktop backend. Tauri/WebView origins vary
    # across platforms and build modes, so allow all origins and avoid
    # credentials to make browser preflight requests deterministic.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return JSON errors with CORS headers so packaged WebView can expose real failures."""
    logger.exception("Unhandled request error on {} {}: {}", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)[:500]},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin") or "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


from app.routers import (  # noqa: E402
    health,
    ideas,
    knowledge,
    papers,
    review,
    search,
    settings as settings_router,
    socratic,
    streaming,
    verification,
    writing,
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(papers.router, prefix="/api/v1", tags=["papers"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])
app.include_router(settings_router.router, prefix="/api/v1", tags=["settings"])
app.include_router(streaming.router, prefix="/api/v1", tags=["streaming"])
app.include_router(ideas.router, prefix="/api/v1", tags=["ideas"])
app.include_router(writing.router, prefix="/api/v1", tags=["writing"])
app.include_router(review.router, prefix="/api/v1", tags=["review"])
app.include_router(verification.router, prefix="/api/v1", tags=["verification"])
app.include_router(socratic.router, prefix="/api/v1", tags=["ideas"])


if __name__ == "__main__":
    # PyInstaller fix: console=False leaves sys.stdout/stderr as None,
    # which crashes uvicorn.logging (calls .isatty() on None).
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    parser = argparse.ArgumentParser(description="Research Assistant backend")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=False,
        log_level=settings.log_level,
    )
