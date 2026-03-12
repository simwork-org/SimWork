from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseModel):
    app_name: str = "SimWork"
    api_prefix: str = "/api/v1"
    model_provider: str = Field(default="ollama", alias="MODEL_PROVIDER")
    model_name: str = Field(default="mistral:latest", alias="MODEL_NAME")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    ollama_endpoint: str = Field(default="http://localhost:11434/v1", alias="OLLAMA_ENDPOINT")
    db_path: Path = Field(default=ROOT_DIR / "backend" / "data" / "simwork.db", alias="SIMWORK_DB_PATH")
    scenarios_path: Path = ROOT_DIR / "scenarios"
    time_limit_minutes: int = 30
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="SIMWORK_CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    values: dict[str, str] = {}
    for field_name, field in Settings.model_fields.items():
        alias = field.alias or field_name
        if alias in os.environ:
            values[alias] = os.environ[alias]
    settings = Settings.model_validate(values)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
