"""Settings routes for providers, usage, data management, and system info."""

import io
import json
import os
import platform
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from time import perf_counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import engine, get_db
from app.database.chroma_client import collection
from app.database.sqlite import (
    AppSetting,
    IdeaHistory,
    LLMProvider as LLMProviderModel,
    LLMUsage,
    MindMapNode,
    Paper,
    PaperRelation,
    PdfAnnotation,
    Project,
    SearchHistory,
    SocraticInsight,
    SocraticMessage,
    SocraticSession,
    WritingProject,
)
from app.llm.router import DEFAULT_BASE_URLS, DEFAULT_MODELS, get_provider_by_id
from app.services.cost_estimator import DEEPSEEK_PRICING, estimate_cost
from app.models import (
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
    ProxyConfig,
    SemanticScholarConfig,
    ThemeUpdate,
)
from app.services.crypto import decrypt_api_key, encrypt_api_key
from app.services.proxy import get_async_client, set_proxy
from app.services.semantic_scholar_api import (
    semantic_scholar_get,
    set_semantic_scholar_api_key,
)
from app.version import __version__

router = APIRouter()


class ProviderTestRequest(BaseModel):
    provider_id: str | None = None


@router.get("/settings/proxy", response_model=ProxyConfig)
def get_proxy_config(db: Session = Depends(get_db)):
    enabled = db.get(AppSetting, "proxy_enabled")
    url = db.get(AppSetting, "proxy_url")
    config = ProxyConfig(
        enabled=enabled is not None and enabled.value == "true",
        url=url.value if url and url.value else "http://127.0.0.1:7897",
    )
    set_proxy(config.url if config.enabled else None)
    return config


@router.put("/settings/proxy", response_model=ProxyConfig)
def update_proxy_config(config: ProxyConfig, db: Session = Depends(get_db)):
    values = {
        "proxy_enabled": "true" if config.enabled else "false",
        "proxy_url": config.url,
    }
    for key, value in values.items():
        setting = db.get(AppSetting, key)
        if setting:
            setting.value = value
        else:
            db.add(AppSetting(key=key, value=value))
    db.commit()
    set_proxy(config.url if config.enabled else None)
    return config


@router.get("/settings/semantic-scholar", response_model=SemanticScholarConfig)
def get_semantic_scholar_config(db: Session = Depends(get_db)):
    setting = db.get(AppSetting, "semantic_scholar_api_key")
    api_key = decrypt_api_key(setting.value) if setting else ""
    set_semantic_scholar_api_key(api_key)
    return SemanticScholarConfig(api_key=api_key)


@router.put("/settings/semantic-scholar", response_model=SemanticScholarConfig)
def update_semantic_scholar_config(
    config: SemanticScholarConfig,
    db: Session = Depends(get_db),
):
    setting = db.get(AppSetting, "semantic_scholar_api_key")
    encrypted_key = encrypt_api_key(config.api_key.strip())
    if setting:
        setting.value = encrypted_key
    else:
        db.add(AppSetting(key="semantic_scholar_api_key", value=encrypted_key))
    db.commit()
    set_semantic_scholar_api_key(config.api_key)
    return SemanticScholarConfig(api_key=config.api_key.strip())


@router.post("/settings/proxy/test")
async def test_proxy_config(config: ProxyConfig):
    started = perf_counter()
    try:
        proxy_override = config.url if config.enabled else None
        async with get_async_client(
            proxy_override=proxy_override,
            timeout=10,
        ) as client:
            response = await semantic_scholar_get(
                client,
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": "test", "limit": 1, "fields": "paperId"},
            )
            response.raise_for_status()
        return {
            "success": True,
            "message": f"Connected successfully (HTTP {response.status_code})",
            "latency_ms": round((perf_counter() - started) * 1000),
        }
    except Exception as exc:
        logger.warning("Proxy connection test failed: {}", exc)
        return {
            "success": False,
            "message": str(exc)[:200] or exc.__class__.__name__,
            "latency_ms": round((perf_counter() - started) * 1000),
        }


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


def _utc_isoformat(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")




def _json_safe(value):
    if isinstance(value, datetime):
        return _utc_isoformat(value)
    return value


def _model_to_dict(row, exclude: set[str] | None = None, extra: dict | None = None) -> dict:
    exclude = exclude or set()
    data = {
        column.name: _json_safe(getattr(row, column.name))
        for column in row.__table__.columns
        if column.name not in exclude
    }
    if extra:
        data.update(extra)
    return data

def _set_only_active(db: Session, provider_id: str) -> None:
    db.query(LLMProviderModel).filter(LLMProviderModel.id != provider_id).update(
        {LLMProviderModel.is_active: False},
        synchronize_session=False,
    )




@router.get("/settings/onboarding-status")
def get_onboarding_status(db: Session = Depends(get_db)):
    """Return whether first-run LLM provider setup has been completed."""
    providers = db.query(LLMProviderModel).all()
    has_api_key = any(bool(decrypt_api_key(provider.api_key or "").strip()) for provider in providers)
    return {
        "has_api_key": has_api_key,
        "has_papers": db.query(Paper).count() > 0,
        "onboarded": has_api_key,
    }


@router.get("/settings/data/export")
def export_all_data(db: Session = Depends(get_db)):
    """Export user metadata as a ZIP archive. Secrets and cached PDF files are excluded."""
    exported_at = datetime.now(timezone.utc)
    buf = io.BytesIO()
    models = [
        ("projects.json", Project),
        ("papers.json", Paper),
        ("pdf_annotations.json", PdfAnnotation),
        ("paper_relations.json", PaperRelation),
        ("mindmap_nodes.json", MindMapNode),
        ("search_histories.json", SearchHistory),
        ("llm_usage.json", LLMUsage),
        ("socratic_messages.json", SocraticMessage),
        ("socratic_insights.json", SocraticInsight),
        ("idea_history.json", IdeaHistory),
        ("writing_projects.json", WritingProject),
    ]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        counts = {}
        for filename, model in models:
            rows = db.query(model).all()
            counts[filename.removesuffix(".json")] = len(rows)
            zf.writestr(
                filename,
                json.dumps([_model_to_dict(row) for row in rows], ensure_ascii=False, indent=2),
            )

        sessions = db.query(SocraticSession).all()
        counts["socratic_sessions"] = len(sessions)
        zf.writestr(
            "socratic_sessions.json",
            json.dumps([_model_to_dict(session) for session in sessions], ensure_ascii=False, indent=2),
        )

        providers = db.query(LLMProviderModel).all()
        counts["llm_providers"] = len(providers)
        zf.writestr(
            "llm_providers.json",
            json.dumps(
                [
                    _model_to_dict(
                        provider,
                        exclude={"api_key"},
                        extra={"has_api_key": bool(decrypt_api_key(provider.api_key or "").strip())},
                    )
                    for provider in providers
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

        writing_root = Path(app_settings.writing_projects_dir)
        writing_file_count = 0
        if writing_root.exists():
            for item in writing_root.rglob("*"):
                if not item.is_file():
                    continue
                try:
                    relative = item.relative_to(writing_root)
                except ValueError:
                    continue
                zf.write(item, f"writing_project_files/{relative.as_posix()}")
                writing_file_count += 1
        counts["writing_project_files"] = writing_file_count

        settings_rows = db.query(AppSetting).all()
        counts["settings"] = len(settings_rows)
        zf.writestr(
            "settings.json",
            json.dumps(
                {
                    row.key: ("<redacted>" if row.key in {"semantic_scholar_api_key"} else row.value)
                    for row in settings_rows
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        zf.writestr(
            "export_info.json",
            json.dumps(
                {
                    "exported_at": exported_at.isoformat().replace("+00:00", "Z"),
                    "version": __version__,
                    "includes_cached_pdfs": False,
                    "includes_api_keys": False,
                    "counts": counts,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    buf.seek(0)
    filename = f"research-assistant-backup-{exported_at.strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    has_cache_details = or_(
        LLMUsage.cache_hit_tokens.isnot(None),
        LLMUsage.cache_miss_tokens.isnot(None),
    )
    cache_row = (
        db.query(
            func.coalesce(func.sum(LLMUsage.cache_hit_tokens), 0),
            func.coalesce(func.sum(LLMUsage.cache_miss_tokens), 0),
        )
        .filter(LLMUsage.timestamp >= window_start)
        .filter(LLMUsage.status == "success")
        .filter(has_cache_details)
        .first()
    )
    cache_hit_tokens = int(cache_row[0] or 0)
    cache_miss_tokens = int(cache_row[1] or 0)
    cache_total = cache_hit_tokens + cache_miss_tokens
    cache_hit_rate = round(cache_hit_tokens / cache_total * 100, 1) if cache_total else None

    priced_rows = (
        db.query(
            LLMUsage.model,
            func.coalesce(func.sum(LLMUsage.cache_hit_tokens), 0),
            func.coalesce(func.sum(LLMUsage.cache_miss_tokens), 0),
            func.coalesce(func.sum(LLMUsage.tokens_out), 0),
        )
        .filter(LLMUsage.timestamp >= window_start)
        .filter(LLMUsage.status == "success")
        .filter(LLMUsage.model.in_(tuple(DEEPSEEK_PRICING)))
        .filter(has_cache_details)
        .group_by(LLMUsage.model)
        .all()
    )
    estimated_cost = 0.0
    cost_by_model = {}
    for model, cache_hit, cache_miss, tokens_out in priced_rows:
        estimate = estimate_cost(model, int(cache_hit), int(cache_miss), int(tokens_out))
        if estimate is None:
            continue
        estimated_cost += estimate["total"]
        cost_by_model[model] = estimate

    return {
        "calls_today": calls_today,
        "calls_week": calls_week,
        "calls_month": calls_month,
        "tokens_in_week": int(token_row[0] or 0),
        "tokens_out_week": int(token_row[1] or 0),
        "cache_hit_rate": cache_hit_rate,
        "cache_hit_tokens": cache_hit_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "estimated_cost": round(estimated_cost, 6),
        "cost_by_model": cost_by_model,
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
            func.coalesce(func.sum(LLMUsage.cache_hit_tokens), 0),
            func.coalesce(func.sum(LLMUsage.cache_miss_tokens), 0),
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
            "cache_hit_tokens": int(cache_hit_tokens or 0),
            "cache_miss_tokens": int(cache_miss_tokens or 0),
        }
        for provider_name, model, calls, tokens_in, tokens_out, cache_hit_tokens, cache_miss_tokens in rows
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
            "timestamp": _utc_isoformat(row.timestamp),
            "provider_name": row.provider_name,
            "model": row.model,
            "function_name": row.function_name,
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
            "duration_ms": row.duration_ms,
            "status": row.status,
            "cache_hit_tokens": row.cache_hit_tokens,
            "cache_miss_tokens": row.cache_miss_tokens,
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
            SocraticInsight,
            SocraticMessage,
            SocraticSession,
            IdeaHistory,
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
    return {"theme": "light"}


@router.patch("/settings/theme")
def update_theme(req: ThemeUpdate):
    if req.theme not in ("dark", "light"):
        raise HTTPException(status_code=400, detail="Theme must be 'dark' or 'light'")
    return {"theme": req.theme}
