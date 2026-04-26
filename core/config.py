"""
Конфигурация приложения через pydantic-settings.

Все секреты и runtime-настройки читаются здесь и только здесь.
Переменные окружения и .env файл подхватываются автоматически.

Пример:
    from core.config import settings
    if not settings.yandex_api_key:
        raise RuntimeError(...)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AppSettings(BaseSettings):
    """Глобальные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    yandex_api_key: Optional[str] = Field(
        default=None,
        validation_alias="YANDEX_API_KEY",
        description="API-ключ Yandex SpeechKit. Обязателен только при использовании TTS.",
    )

    log_level: str = Field(
        default="INFO",
        validation_alias="AA_LOG_LEVEL",
        description="Уровень логирования (DEBUG/INFO/WARNING/ERROR).",
    )


# Единый импортируемый экземпляр настроек.
settings = AppSettings()
