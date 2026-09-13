from __future__ import annotations

import os
from dataclasses import dataclass


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError(
            "DATABASE_URL is required. Set it to the local PostgreSQL URL, "
            "for example: postgresql+psycopg://USER:PASSWORD@localhost:5432/avasya"
        )
    return value


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = _database_url()
    DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    POSTGIS_SRID: int = int(os.getenv("POSTGIS_SRID", "4326"))
    APP_ENV: str = os.getenv("APP_ENV", "development")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
