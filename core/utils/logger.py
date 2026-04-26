"""
Фабрика логгеров.

Используется во всём проекте вместо print/traceback.print_exc().
Гарантирует единый формат и единственную инициализацию хендлеров.

Пример:
    from core.utils.logger import LoggerFactory
    log = LoggerFactory.get_logger(__name__)
    log.info("started")
    log.exception("failure during render")
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional


class LoggerFactory:
    """Фабрика логгеров с ленивой инициализацией корневого хендлера."""

    _initialized: bool = False
    _default_level: int = logging.INFO
    _format: str = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    _datefmt: str = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def _init_root(cls) -> None:
        """Один раз настроить корневой логгер для приложения."""
        if cls._initialized:
            return

        # Уровень из переменной окружения, по умолчанию INFO
        level_name = os.environ.get("AA_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        cls._default_level = level

        root = logging.getLogger("aa_video_builder")
        root.setLevel(level)
        # не размножаем хендлеры при повторных импортах
        if not root.handlers:
            handler = logging.StreamHandler(stream=sys.stderr)
            handler.setFormatter(logging.Formatter(fmt=cls._format, datefmt=cls._datefmt))
            handler.setLevel(level)
            root.addHandler(handler)
        # отключаем propagation на global root, чтобы не дублировались сообщения
        root.propagate = False
        cls._initialized = True

    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """Получить логгер с заданным именем (как правило, __name__)."""
        cls._init_root()
        if not name:
            name = "aa_video_builder"
        # Все логгеры приложения наследуем от корневого "aa_video_builder"
        if not name.startswith("aa_video_builder"):
            name = f"aa_video_builder.{name}"
        logger = logging.getLogger(name)
        logger.setLevel(cls._default_level)
        return logger

    @classmethod
    def set_level(cls, level: int | str) -> None:
        """Изменить уровень логирования глобально."""
        cls._init_root()
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        cls._default_level = level
        logging.getLogger("aa_video_builder").setLevel(level)
        for h in logging.getLogger("aa_video_builder").handlers:
            h.setLevel(level)
