"""Research Assistant Backend — FastAPI entry point."""

import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logs import setup_logging
from app.version import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize process-wide services."""
    setup_logging()
    yield


app = FastAPI(
    title="Research Assistant API",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
