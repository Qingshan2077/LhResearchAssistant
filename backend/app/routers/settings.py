"""设置路由 — LLM Provider 管理 + 主题"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.database.sqlite import LLMProvider as LLMProviderModel
from app.models import ProviderCreate, ProviderResponse, ThemeUpdate
from app.llm.router import get_provider_by_id, PROVIDER_MAP, DEFAULT_BASE_URLS, DEFAULT_MODELS

router = APIRouter()


@router.get("/settings/providers", response_model=list[ProviderResponse])
def list_providers(db: Session = Depends(get_db)):
    """获取所有 LLM Provider 配置"""
    providers = db.query(LLMProviderModel).order_by(LLMProviderModel.priority.desc()).all()
    return providers


@router.post("/settings/providers", response_model=ProviderResponse)
def create_provider(req: ProviderCreate, db: Session = Depends(get_db)):
    """添加 LLM Provider 配置"""
    provider = LLMProviderModel(
        name=req.name,
        display_name=req.display_name or req.name,
        api_key=req.api_key,
        base_url=req.base_url or DEFAULT_BASE_URLS.get(req.name, ""),
        default_model=req.default_model or DEFAULT_MODELS.get(req.name, ""),
        is_active=req.is_active,
        priority=req.priority,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


@router.patch("/settings/providers/{provider_id}", response_model=ProviderResponse)
def update_provider(provider_id: str, req: ProviderCreate, db: Session = Depends(get_db)):
    """更新 Provider"""
    provider = db.query(LLMProviderModel).filter(LLMProviderModel.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    for field in ["name", "display_name", "api_key", "base_url", "default_model",
                  "is_active", "priority", "max_tokens", "temperature"]:
        val = getattr(req, field, None)
        if val is not None:
            setattr(provider, field, val)

    db.commit()
    db.refresh(provider)
    return provider


@router.delete("/settings/providers/{provider_id}")
def delete_provider(provider_id: str, db: Session = Depends(get_db)):
    provider = db.query(LLMProviderModel).filter(LLMProviderModel.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    return {"deleted": True}


@router.post("/settings/providers/test")
async def test_provider(provider_id: str | None = None, db: Session = Depends(get_db)):
    """测试 Provider 连接"""
    if provider_id:
        result = get_provider_by_id(provider_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Provider not found")
        provider_impl, config = result
    else:
        # 测试默认 DeepSeek
        from app.llm.deepseek import DeepSeekProvider
        from app.llm import LLMConfig
        provider_impl = DeepSeekProvider()
        config = LLMConfig()

    return await provider_impl.test_connection(config)


@router.get("/settings/theme")
def get_theme():
    """获取当前主题（存储在服务器内存中，实际应存 DB 或配置文件）"""
    return {"theme": "dark"}


@router.patch("/settings/theme")
def update_theme(req: ThemeUpdate):
    if req.theme not in ("dark", "light"):
        raise HTTPException(status_code=400, detail="Theme must be 'dark' or 'light'")
    return {"theme": req.theme}
