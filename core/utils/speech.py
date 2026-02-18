import hashlib
import os
import wave
from pathlib import Path

from dotenv import load_dotenv
from speechkit import model_repository, configure_credentials, creds

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "output" / "audio_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")

if YANDEX_API_KEY:
    configure_credentials(yandex_credentials=creds.YandexCredentials(api_key=YANDEX_API_KEY))
else:
    print("YANDEX_API_KEY не найден в .env файле")


def get_wav_duration(filepath: str) -> float:
    """возвращает длительность WAV файла в секундах."""
    try:
        with wave.open(filepath, "rb") as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except Exception as e:
        print(f"ошибка при чтении длительности аудио: {e}")
        return 0.0


def generate_speech(text: str, voice: str = "zahar", lang: str = "ru-RU") -> tuple[str, float]:
    """
    1. проверка кэша.
    2. если нет в кэше — синтез через API.
    3. возвращает (путь_к_файлу, длительность).
    """
    if not text:
        return "", 0.0

    # Генерируем уникальный ключ на основе текста, голоса и языка
    text_hash = hashlib.md5(f"{text}_{voice}_{lang}".encode()).hexdigest()
    file_path = CACHE_DIR / f"{text_hash}.wav"
    str_path = str(file_path)

    if file_path.exists():
        return str_path, get_wav_duration(str_path)

    try:
        print(f"Синтез речи для: '{text[:30]}...' ({voice})")
        model = model_repository.synthesis_model()
        model.voice = voice
        model.language = lang
        model.role = "good"

        result = model.synthesize(text, raw_format=False)
        result.export(str_path, "wav")
        return str_path, get_wav_duration(str_path)
    except Exception as e:
        print(f"ошибка Yandex SpeechKit: {e}")
        return "", 0.0


# backward-compatible wrappers for older live mode paths

def start_speech(filepath: str, tts: str, lang: str, voice: str):
    audio_path, _ = generate_speech(tts, voice=voice, lang=lang)
    if not audio_path:
        return

    # Если путь назначения отличается от кэша, копируем файл
    if audio_path != filepath:
        try:
            with open(audio_path, "rb") as src, open(filepath, "wb") as dst:
                dst.write(src.read())
        except Exception:
            pass