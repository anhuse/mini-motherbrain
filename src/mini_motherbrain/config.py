from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration (prefix MMB_, loaded from .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MMB_", extra="ignore")

    es_url: str = "http://localhost:9200"
    es_user: str = "elastic"
    es_password: str = "changeme"
    companies_index: str = "companies"
    # Landing zone for raw source files (e.g. the Brreg bulk dump).
    data_dir: Path = Path("data")


settings = Settings()
