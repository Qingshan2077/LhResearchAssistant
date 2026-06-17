"""Research Assistant Backend — FastAPI 入口"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.database.sqlite import ensure_runtime_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表，关闭时清理"""
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)
    yield


app = FastAPI(
    title="Research Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 允许 Tauri WebView 和 Vite Dev Server 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──────────────────────────────────────────
# 每个路由模块注册时自动挂载
from app.routers import health, search, papers, knowledge, settings as settings_router, streaming, ideas, writing, review, verification, socratic

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
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level,
    )
