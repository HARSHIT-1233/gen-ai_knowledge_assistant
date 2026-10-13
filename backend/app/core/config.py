
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GenAI Knowledge & Research Assistant"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    api_v1_prefix: str = "/api/v1"

    # Used in a later phase when we connect Ollama.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_embed_model: str = "nomic-embed-text"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them."""
    return Settings()
