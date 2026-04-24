from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MO_", env_file=".env", extra="ignore")

    db_dsn: str = Field(default="postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator")
    http_port: int = 8765
    embed_model: str = "BAAI/bge-small-zh-v1.5"
    embed_dim: int = 512
    log_level: str = "DEBUG"

    extraction_base_url: str = Field(default="", validation_alias="MO_EXTRACTION_BASE_URL")
    extraction_model: str = Field(default="gpt-4o-mini", validation_alias="MO_EXTRACTION_MODEL")
    extraction_api_key: str = Field(default="local", validation_alias="MO_EXTRACTION_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
