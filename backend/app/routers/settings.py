"""Settings routes for providers, usage, data management, and system info."""

import os
import platform
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import engine, get_db
from app.database.chroma_client import collection
from app.database.sqlite import (
    LLMProvider as LLMProviderModel,
    LLMUsage,
    MindMapNode,
    Paper,
    PaperRelation,
    Project,
    SearchHistory,
    WritingProject,
)
from app.llm.router import DEFAULT_BASE_URLS, DEFAULT_MODELS, get_provider_by_id
from app.models import ProviderCreate, ProviderResponse, ProviderUpdate, ThemeUpdate
from app.services.crypto import decrypt_api_key, encrypt_api_key
from app.version import __version__

router = APIRouter()


class ProviderTestRequest(BaseModel):
    provider_id: str | None = None


def _provider_to_response(provider: LLMProviderModel) -> dict:
    """Expose a decrypted key to the local settings UI, never the stored ciphertext."""
    return {
        "id": provider.id,
        "name": provider.name,
        "display_name": provider.display_name or "",
        "api_key": decrypt_api_key(provider.api_key or ""),
        "base_url": provider.base_url or "",
        "default_model": provider.default_model or "",
        "is_active": bool(provider.is_active),
        "priority": provider.priority or 0,
        "max_tokens": provider.max_tokens or 8192,
        "temperature": provider.temperature if provider.temperature is not None else 0.7,
        "last_test_at": provider.last_test_at,
        "last_test_success": provider.last_test_success,
        "last_test_latency": provider.last_test_latency or 0,
    }


def _dir_size(path: str) -> int:
    root = Path(path)
    if not root.exists():
        return 0
    total = 0
    for item in root.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError as exc:
                logger.warning("Could not inspect file {}: {}", item, exc)
    return total


def _clear_directory(path: str) -> None:
    root = Path(path)
    if not root.exists():
        return
    for child in root.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError as exc:
            logger.warning("Could not remove cached path {}: {}", child, exc)


def _mb(size_bytes: int) -> float:
    return round(size_bytes / 1024 / 1024, 2)


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(1, days))


def _set_only_active(db: Session, provider_id: str) -> None:
    db.query(LLMProviderModel).filter(LLMProviderModel.id != provider_id).update(
        {LLMProviderModel.is_active: False},
        synchronize_session=False,
    )


@router.get("/settings/providers", response_model=list[ProviderResponse])
def list_providers(db: Session = Depends(get_db)):
    providers = db.query(LLMProviderModel).order_by(LLMProviderModel.priority.desc()).all()
    return [_provider_to_response(provider) for provider in providers]


@router.post("/settings/providers", response_model=ProviderResponse)
def create_provider(req: ProviderCreate, db: Session = Depends(get_db)):
    provider = LLMProviderModel(
        name=req.name,
        display_name=req.display_name or req.name,
        api_key=encrypt_api_key(req.api_key),
        base_url=req.base_url or DEFAULT_BASE_URLS.get(req.name, ""),
        default_model=req.default_model or DEFAULT_MODELS.get(req.name, ""),
        is_active=req.is_active,
        priority=req.priority,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    db.add(provider)
    db.flush()
    if provider.is_active:
        _set_only_active(db, provider.id)
    db.commit()
    db.refresh(provider)
    logger.info("Created LLM provider {}", provider.id)
    return _provider_to_response(provider)


@router.patch("/settings/providers/{provider_id}", response_model=ProviderResponse)
def update_provider(provider_id: str, req: ProviderUpdate, db: Session = Depends(get_db)):
    provider = db.query(LLMProviderModel).filter(LLMProviderModel.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    patch_data = req.model_dump(exclude_unset=True)
    if patch_data.get("is_active") is True:
        _set_only_active(db, provider_id)
    if "api_key" in patch_data:
        patch_data["api_key"] = encrypt_api_key(patch_data["api_key"] or "")
    for field, value in patch_data.items():
        setattr(provider, field, value)

    db.commit()
    db.refresh(provider)
    logger.info("Updated LLM provider {}", provider_id)
    return _provider_to_response(provider)


@router.delete("/settings/providers/{provider_id}")
def delete_provider(provider_id: str, db: Session = Depends(get_db)):
    provider = db.query(LLMProviderModel).filter(LLMProviderModel.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    logger.info("Deleted LLM provider {}", provider_id)
    return {"deleted": True}


@router.post("/settings/providers/test")
async def test_provider(req: ProviderTestRequest, db: Session = Depends(get_db)):
    if req.provider_id:
        record = db.query(LLMProviderModel).filter(LLMProviderModel.id == req.provider_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Provider not found")
        result = get_provider_by_id(req.provider_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Provider not found")
        provider_impl, config = result
    else:
        record = None
        from app.llm import LLMConfig
        from app.llm.deepseek import DeepSeekProvider

        provider_impl = DeepSeekProvider()
        config = LLMConfig()

    result = await provider_impl.test_connection(config)
    if record:
        record.last_test_at = datetime.now(timezone.utc)
        record.last_test_success = bool(result.get("success"))
        record.last_test_latency = int(result.get("latency_ms") or 0)
        db.commit()
    return result


@router.get("/settings/usage/summary")
def usage_summary(days: int = 7, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    day_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    window_start = _since(days)
    calls_today = db.query(LLMUsage).filter(LLMUsage.timestamp >= day_start).count()
    calls_week = db.query(LLMUsage).filter(LLMUsage.timestamp >= week_start).count()
    calls_month = db.query(LLMUsage).filter(LLMUsage.timestamp >= month_start).count()
    token_row = (
        db.query(
            func.coalesce(func.sum(LLMUsage.tokens_in), 0),
            func.coalesce(func.sum(LLMUsage.tokens_out), 0),
        )
        .filter(LLMUsage.timestamp >= window_start)
        .first()
    )
    return {
        "calls_today": calls_today,
        "calls_week": calls_week,
        "calls_month": calls_month,
        "tokens_in_week": int(token_row[0] or 0),
        "tokens_out_week": int(token_row[1] or 0),
    }


@router.get("/settings/usage/by-provider")
def usage_by_provider(days: int = 7, db: Session = Depends(get_db)):
    rows = (
        db.query(
            LLMUsage.provider_name,
            LLMUsage.model,
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.tokens_in), 0),
            func.coalesce(func.sum(LLMUsage.tokens_out), 0),
        )
        .filter(LLMUsage.timestamp >= _since(days))
        .group_by(LLMUsage.provider_name, LLMUsage.model)
        .order_by(func.count(LLMUsage.id).desc())
        .all()
    )
    return [
        {
            "provider_name": provider_name or "default",
            "model": model or "",
            "calls": calls,
            "tokens_in": int(tokens_in or 0),
            "tokens_out": int(tokens_out or 0),
        }
        for provider_name, model, calls, tokens_in, tokens_out in rows
    ]


@router.get("/settings/usage/by-function")
def usage_by_function(days: int = 7, db: Session = Depends(get_db)):
    rows = (
        db.query(
            LLMUsage.function_name,
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.tokens_in), 0),
            func.coalesce(func.sum(LLMUsage.tokens_out), 0),
        )
        .filter(LLMUsage.timestamp >= _since(days))
        .group_by(LLMUsage.function_name)
        .order_by(func.count(LLMUsage.id).desc())
        .all()
    )
    total = sum(int(row[2] or 0) + int(row[3] or 0) for row in rows) or 1
    return [
        {
            "function_name": function_name or "chat",
            "calls": calls,
            "tokens_total": int(tokens_in or 0) + int(tokens_out or 0),
            "percentage": round(
                ((int(tokens_in or 0) + int(tokens_out or 0)) / total) * 100,
                1,
            ),
        }
        for function_name, calls, tokens_in, tokens_out in rows
    ]


@router.get("/settings/usage/recent")
def usage_recent(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(LLMUsage)
        .order_by(LLMUsage.timestamp.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [
        {
            "id": row.id,
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
            "provider_name": row.provider_name,
            "model": row.model,
            "function_name": row.function_name,
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
            "duration_ms": row.duration_ms,
            "status": row.status,
        }
        for row in rows
    ]


@router.get("/settings/data/stats")
def data_stats(db: Session = Depends(get_db)):
    try:
        chroma_count = collection.count()
    except Exception as exc:
        logger.warning("Could not read Chroma collection size: {}", exc)
        chroma_count = 0
    db_path = Path(app_settings.db_path)
    db_size = db_path.stat().st_size if db_path.exists() else 0
    return {
        "paper_count": db.query(Paper).count(),
        "chroma_count": chroma_count,
        "writing_project_count": db.query(WritingProject).count(),
        "provider_count": db.query(LLMProviderModel).count(),
        "cache_size_mb": _mb(_dir_size(app_settings.papers_cache_dir)),
        "db_size_mb": _mb(db_size),
        "cache_path": app_settings.papers_cache_dir,
    }


@router.post("/settings/data/clear-vector-cache")
def clear_vector_cache():
    try:
        ids = collection.get().get("ids", [])
        if ids:
            collection.delete(ids=ids)
        logger.info("Cleared {} vector records", len(ids))
        return {"cleared": True, "count": len(ids)}
    except Exception as exc:
        logger.exception("Could not clear vector cache")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/settings/data/clear-all-data")
def clear_all_data(db: Session = Depends(get_db)):
    """Securely remove user research data while preserving provider settings."""
    try:
        for model in (
            MindMapNode,
            PaperRelation,
            SearchHistory,
            WritingProject,
            LLMUsage,
            Paper,
            Project,
        ):
            db.query(model).delete(synchronize_session=False)
        db.commit()

        try:
            ids = collection.get().get("ids", [])
            if ids:
                collection.delete(ids=ids)
        except Exception as exc:
            logger.warning("Database cleared but Chroma cleanup failed: {}", exc)

        _clear_directory(app_settings.papers_cache_dir)
        _clear_directory(app_settings.writing_projects_dir)

        raw_connection = engine.raw_connection()
        try:
            cursor = raw_connection.cursor()
            try:
                cursor.execute("VACUUM")
            finally:
                cursor.close()
        finally:
            raw_connection.close()
        logger.warning("All research data was securely cleared")
        return {"status": "ok", "message": "All user data cleared."}
    except Exception as exc:
        db.rollback()
        logger.exception("Secure data clearing failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/settings/system-info")
def system_info():
    return {
        "backend_version": __version__,
        "python_version": platform.python_version(),
        "db_path": app_settings.db_path,
        "cache_path": app_settings.papers_cache_dir,
        "cache_size_mb": _mb(_dir_size(app_settings.papers_cache_dir)),
        "chroma_path": app_settings.chroma_dir,
        "data_dir": app_settings.data_dir,
        "cwd": os.getcwd(),
    }


@router.get("/settings/theme")
def get_theme():
    return {"theme": "dark"}


@router.patch("/settings/theme")
def update_theme(req: ThemeUpdate):
    if req.theme not in ("dark", "light"):
        raise HTTPException(status_code=400, detail="Theme must be 'dark' or 'light'")
    return {"theme": req.theme}
