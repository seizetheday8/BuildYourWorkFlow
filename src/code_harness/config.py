"""Configuration loading from .env and environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str = Field(..., alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        alias="DEEPSEEK_BASE_URL",
    )
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    log_dir: Path = Field(default=Path("./logs"), alias="LOG_DIR")

    # 模型单价（USD / 1M tokens）—— Phase 0 默认按 DeepSeek V4 定价折算
    price_input_per_million: float = 0.43
    price_cache_hit_per_million: float = 0.0036
    price_output_per_million: float = 0.86


def load_settings() -> Settings:
    """Load settings from environment."""
    return Settings()  # type: ignore[call-arg]
