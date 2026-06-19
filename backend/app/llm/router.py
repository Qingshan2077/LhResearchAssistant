"""LLM Provider 路由 — 根据 DB 配置选择活跃 Provider"""

from sqlalchemy.orm import Session

from app.database.sqlite import LLMProvider as LLMProviderModel
from app.llm import LLMProvider, LLMConfig
from app.llm.deepseek import DeepSeekProvider
from app.llm.openai_compat import OpenAICompatibleProvider
from app.llm.ollama import OllamaProvider
from app.config import settings
from app.database.usage_tracker import UsageTrackingProvider

# Provider 类映射
PROVIDER_MAP: dict[str, type[LLMProvider]] = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAICompatibleProvider,
    "claude": OpenAICompatibleProvider,    # Claude API 也是 OpenAI 兼容
    "ollama": OllamaProvider,
    "custom": OpenAICompatibleProvider,
}

# 默认 base_url 映射
DEFAULT_BASE_URLS: dict[str, str] = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
}

# 默认模型映射
DEFAULT_MODELS: dict[str, str] = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "ollama": "qwen2.5:7b",
}


def get_active_provider(db: Session) -> tuple[LLMProvider, LLMConfig]:
    """从 DB 获取最高优先级的活跃 Provider。无配置时返回 DeepSeek（无 key 的占位）"""
    record = (
        db.query(LLMProviderModel)
        .filter(LLMProviderModel.is_active)
        .order_by(LLMProviderModel.priority.desc())
        .first()
    )

    if record is None:
        # 兜底：默认 DeepSeek（可能无 key）
        cls = DeepSeekProvider
        cfg = LLMConfig(
            api_key=settings.default_deepseek_api_key,
            base_url=settings.default_deepseek_base_url,
            model=settings.default_deepseek_model,
        )
        return UsageTrackingProvider(cls(), db, provider_name="deepseek"), cfg

    cls = PROVIDER_MAP.get(record.name, OpenAICompatibleProvider)
    cfg = LLMConfig(
        api_key=record.api_key,
        base_url=record.base_url or DEFAULT_BASE_URLS.get(record.name, ""),
        model=record.default_model or DEFAULT_MODELS.get(record.name, ""),
        max_tokens=record.max_tokens,
        temperature=record.temperature,
    )
    provider_name = record.display_name or record.name
    return UsageTrackingProvider(cls(), db, provider_id=record.id, provider_name=provider_name), cfg


def get_provider_by_id(provider_id: str, db: Session) -> tuple[LLMProvider, LLMConfig] | None:
    """根据 provider_id 获取特定 Provider"""
    record = db.query(LLMProviderModel).filter(LLMProviderModel.id == provider_id).first()
    if not record:
        return None

    cls = PROVIDER_MAP.get(record.name, OpenAICompatibleProvider)
    cfg = LLMConfig(
        api_key=record.api_key,
        base_url=record.base_url or DEFAULT_BASE_URLS.get(record.name, ""),
        model=record.default_model or DEFAULT_MODELS.get(record.name, ""),
        max_tokens=record.max_tokens,
        temperature=record.temperature,
    )
    provider_name = record.display_name or record.name
    return UsageTrackingProvider(cls(), db, provider_id=record.id, provider_name=provider_name), cfg
