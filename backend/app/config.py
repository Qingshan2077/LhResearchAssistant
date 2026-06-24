"""全局配置"""

import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings


def _default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        legacy_dir = Path.cwd() / "data"
        if (legacy_dir / "papers.db").is_file():
            return legacy_dir
        local_app_data = os.environ.get("LOCALAPPDATA")
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base_dir / "Research Assistant" / "data"
    return Path("./data")


_DATA_DIR = _default_data_dir()


class Settings(BaseSettings):
    # 服务
    host: str = "localhost"
    port: int = 8787
    log_level: str = "info"

    # 数据路径
    data_dir: str = str(_DATA_DIR)
    chroma_dir: str = str(_DATA_DIR / "chroma_db")
    db_path: str = str(_DATA_DIR / "papers.db")
    papers_cache_dir: str = str(_DATA_DIR / "papers_cache")
    writing_projects_dir: str = str(_DATA_DIR / "writing_projects")
    graphml_path: str = str(_DATA_DIR / "knowledge_graph.graphml")

    # CORS
    cors_origins: str = (
        "http://localhost:1420,"
        "http://127.0.0.1:1420,"
        "http://localhost:8787,"
        "http://127.0.0.1:8787,"
        "http://tauri.localhost,"
        "https://tauri.localhost,"
        "tauri://localhost,"
        "null"
    )

    # 默认 LLM（用户未配置时）
    default_deepseek_api_key: str = ""
    default_deepseek_base_url: str = "https://api.deepseek.com"
    default_deepseek_model: str = "deepseek-v4-flash"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# 确保数据目录存在
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
Path(settings.papers_cache_dir).mkdir(parents=True, exist_ok=True)
Path(settings.writing_projects_dir).mkdir(parents=True, exist_ok=True)
