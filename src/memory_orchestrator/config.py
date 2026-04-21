from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MO_", env_file=".env", extra="ignore")

    db_dsn: str = Field(default="postgresql+asyncpg://postgres:1234@localhost:5433/memory_orchestrator")
    http_port: int = 8765
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    haiku_model: str = "claude-haiku-4-5"
    log_level: str = "INFO"

    anthropic_base_url: str = Field(default="", validation_alias="ANTHROPIC_BASE_URL")
    anthropic_auth_token: str = Field(default="", validation_alias="ANTHROPIC_AUTH_TOKEN")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
