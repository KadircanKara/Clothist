from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://clothist:clothist_dev@localhost:5432/clothist",
        alias="DATABASE_URL",
    )

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_cors_origins: str = Field(
        default="http://localhost:3000",
        alias="API_CORS_ORIGINS",
        description="Comma-separated list of allowed origins.",
    )

    scraper_user_agent: str = Field(
        default="ClothistBot/0.1 (+https://example.com)",
        alias="SCRAPER_USER_AGENT",
    )
    scraper_request_timeout: float = Field(default=20.0, alias="SCRAPER_REQUEST_TIMEOUT")
    scraper_rate_limit_seconds: float = Field(default=1.5, alias="SCRAPER_RATE_LIMIT_SECONDS")

    # LLM provider (OpenAI-compatible). Default: Google Gemini.
    # Swap by changing LLM_BASE_URL + LLM_MODEL — code is provider-agnostic.
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        alias="LLM_BASE_URL",
    )
    llm_model: str = Field(default="gemini-2.0-flash", alias="LLM_MODEL")
    # Reserved for manual fallback on provider deprecation: change one env var
    # and restart. No orchestration logic in MVP.
    llm_model_fallback: str = Field(
        default="llama-3.1-8b-instant",
        alias="LLM_MODEL_FALLBACK",
    )
    llm_timeout_seconds: float = Field(default=12.0, alias="LLM_TIMEOUT_SECONDS")

    # In production logs, hash the raw query to a 16-char SHA-256 prefix
    # instead of logging it verbatim. Dev (default) leaves queries readable.
    log_redact_queries: bool = Field(default=False, alias="LOG_REDACT_QUERIES")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
