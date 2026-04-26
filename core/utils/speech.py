"""
Синтез речи через Yandex SpeechKit.

YANDEX_API_KEY не обязателен в целом, но обязателен и должен быть валидным
для функций синтеза речи. Если TTS вызывается без ключа или с невалидным,
функция явно поднимает исключение и останавливает пайплайн.
"""
from __future__ import annotations

import hashlib
import shutil
import wave
from pathlib import Path
from typing import Tuple

from speechkit import configure_credentials, creds, model_repository

from core.config import settings
from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "output" / "audio_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class SpeechConfigurationError(RuntimeError):
    """Невозможно настроить TTS (нет/невалидный API-ключ)."""


class SpeechSynthesisError(RuntimeError):
    """Ошибка синтеза речи на стороне SpeechKit."""


_credentials_configured = False


def _ensure_credentials() -> None:
    """Лениво настраивает SpeechKit. Кидает понятное исключение, если ключа нет."""
    global _credentials_configured
    if _credentials_configured:
        return

    if not settings.yandex_api_key:
        raise SpeechConfigurationError(
            "YANDEX_API_KEY не задан. Для синтеза речи (TTS) ключ обязателен. "
            "Укажите его в .env или переменных окружения."
        )

    try:
        configure_credentials(
            yandex_credentials=creds.YandexCredentials(api_key=settings.yandex_api_key)
        )
    except Exception as exc:
        raise SpeechConfigurationError(
            f"Не удалось настроить Yandex SpeechKit с переданным YANDEX_API_KEY: {exc}"
        ) from exc

    _credentials_configured = True


def get_wav_duration(filepath: str) -> float:
    """Возвращает длительность WAV-файла в секундах."""
    try:
        with wave.open(filepath, "rb") as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except Exception as e:
        log.error("Ошибка при чтении длительности аудио %s: %s", filepath, e)
        return 0.0


def generate_speech(
    text: str,
    voice: str = "zahar",
    lang: str = "ru-RU",
    speed: float = 1.0,
    role: str = "good",
) -> Tuple[str, float]:
    """
    Синтез речи через Yandex SpeechKit с локальным кэшированием.

    Возвращает (путь_к_файлу, длительность_в_секундах).

    Кидает SpeechConfigurationError, если YANDEX_API_KEY отсутствует.
    Кидает SpeechSynthesisError при ошибке синтеза.
    """
    if not text or not str(text).strip():
        return "", 0.0

    _ensure_credentials()

    norm_speed = max(0.6, min(1.8, float(speed)))
    cache_key = f"{text}_{voice}_{lang}_{norm_speed}_{role}"
    text_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
    file_path = CACHE_DIR / f"{text_hash}.wav"
    str_path = str(file_path)

    if file_path.exists():
        return str_path, get_wav_duration(str_path)

    try:
        log.info("Синтез речи для: '%s...' (voice=%s, lang=%s, speed=%.2f)",
                 text[:40], voice, lang, norm_speed)
        model = model_repository.synthesis_model()
        model.voice = voice
        model.language = lang
        model.speed = norm_speed
        model.role = role

        result = model.synthesize(text, raw_format=False)
        result.export(str_path, "wav")
    except Exception as exc:
        log.error("Ошибка Yandex SpeechKit при синтезе: %s", exc)
        raise SpeechSynthesisError(
            f"Не удалось синтезировать речь через Yandex SpeechKit: {exc}"
        ) from exc

    return str_path, get_wav_duration(str_path)


def _normalize_lang(lang: str) -> str:
    """
    Преобразует короткий код языка ('ru'/'en') в формат SpeechKit ('ru-RU'/'en-US').
    Полные коды (с дефисом) пропускает как есть.
    """
    if not lang:
        return "ru-RU"
    if "-" in lang:
        return lang
    table = {"ru": "ru-RU", "en": "en-US"}
    return table.get(lang.lower(), lang)


def start_speech(filepath: str, tts: str, lang: str, voice: str) -> None:
    """
    Backward-compatible обёртка для live mode.

    Синтезирует TTS и копирует/перемещает результат по запрошенному пути filepath.
    """
    audio_path, _ = generate_speech(tts, voice=voice, lang=_normalize_lang(lang))
    if not audio_path:
        return

    if audio_path != filepath:
        try:
            shutil.copyfile(audio_path, filepath)
        except OSError as exc:
            log.warning("Не удалось скопировать аудио из кэша в %s: %s", filepath, exc)
