"""全局配置"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务
    host: str = "localhost"
    port: int = 8787
    log_level: str = "info"

    # 数据路径
    data_dir: str = "./data"
    chroma_dir: str = "./data/chroma_db"
    db_path: str = "./data/papers.db"
    papers_cache_dir: str = "./data/papers_cache"
    graphml_path: str = "./data/knowledge_graph.graphml"

    # CORS
    cors_origins: str = "http://localhost:1420,tauri://localhost"

    # 默认 LLM（用户未配置时）
    default_deepseek_api_key: str = ""
    default_deepseek_base_url: str = "https://api.deepseek.com"
    default_deepseek_model: str = "deepseek-chat"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# 确保数据目录存在
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
Path(settings.papers_cache_dir).mkdir(parents=True, exist_ok=True)
