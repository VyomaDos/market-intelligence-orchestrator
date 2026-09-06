from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ydc_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = "gpt-4.1-mini"
    search_results_per_query: int = Field(default=8, ge=1, le=100)
    search_freshness: str = "month"
    max_concurrency: int = Field(default=3, ge=1, le=10)
    request_timeout_seconds: float = Field(default=30, gt=0)
    ydc_cost_per_1000_calls: float = Field(default=5.0, ge=0)
    llm_input_cost_per_million: float = Field(default=0.40, ge=0)
    llm_cached_input_cost_per_million: float = Field(default=0.10, ge=0)
    llm_output_cost_per_million: float = Field(default=1.60, ge=0)

    def validate_live_keys(self) -> None:
        values = {"YDC_API_KEY": self.ydc_api_key, "OPENAI_API_KEY": self.openai_api_key}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment variable(s): {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
