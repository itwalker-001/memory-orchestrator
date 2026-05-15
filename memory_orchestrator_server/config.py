from functools import lru_cache
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PKG_ROOT = Path(__file__).parent  # memory_orchestrator_server/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MO_",
        env_file=[str(_PKG_ROOT / ".env"), ".env"],
        extra="ignore",
    )

    db_dsn: str = Field(default="postgresql+asyncpg://postgres:1234@localhost:5432/memory_orchestrator")
    http_host: str = "127.0.0.1"
    http_port: int = 8765
    embed_model: str = str(_PKG_ROOT / "models" / "BAAI" / "bge-m3")
    embed_dim: int = 1024
    rerank_model: str = str(_PKG_ROOT / "models" / "BAAI" / "bge-reranker-v2-m3")
    log_level: str = "DEBUG"
    log_dir: str = str(Path.cwd() / "logs")

    @model_validator(mode="after")
    def _resolve_model_paths(self) -> "Settings":
        for field in ("embed_model", "rerank_model"):
            p = Path(getattr(self, field))
            if not p.is_absolute():
                setattr(self, field, str(_PKG_ROOT / p))
        return self

    extraction_base_url: str = Field(default="", validation_alias="MO_EXTRACTION_BASE_URL")
    extraction_model: str = Field(default="gpt-4o-mini", validation_alias="MO_EXTRACTION_MODEL")
    extraction_api_key: str = Field(default="local", validation_alias="MO_EXTRACTION_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
