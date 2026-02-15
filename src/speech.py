# Интеграция с Google Cloud Text-to-Speech или Azure Speech Services
# Локальная альтернатива: TTS модель (например, VITS или Tacotron2)
# Генерация WAV/MP3 файлов аудио
# from google_speech import Speech
#
# def start_speech(filename: str, text: str, lang: str):
#     """Создаёт mp3 файл с названием filename по TTS (Google Speech) из text."""
#     speech = Speech(text, lang)
#     speech.play()
#
#     # you can also apply audio effects while playing (using SoX)
#     # see http://sox.sourceforge.net/sox.html#EFFECTS for full effect documentation
#     # sox_effects = ("speed", "1.5")
#     # speech.play(sox_effects)
#
#     # save the speech to an MP3 file (no effect is applied)
#     speech.save(f"{filename}.mp3")

# FASTAPI APP FOR ACCESS TO THIS PROJECT OVER INTERNET

from argparse import ArgumentParser
from dotenv import load_dotenv
from os import getenv
import wave

from speechkit import model_repository, configure_credentials, creds

load_dotenv()

# Аутентификация через API-ключ.
configure_credentials(
   yandex_credentials=creds.YandexCredentials(
      api_key=getenv("YANDEX_API_KEY"),
   )
)

def start_speech(filepath, tts, lang, voice):
   model = model_repository.synthesis_model()

   # Задайте настройки синтеза.
   model.voice = voice
   model.role = 'good'

   # Синтез речи и создание аудио с результатом.
   result = model.synthesize(tts, raw_format=False)
   result.export(filepath, 'wav')

def get_wav_duration(filepath: str):
    with wave.open(filepath, 'rb') as wav_file:
        n_frames = wav_file.getnframes()
        frame_rate = wav_file.getframerate()
        duration = n_frames / float(frame_rate)
        return duration

if __name__ == '__main__':
   text = "Привет, это проверка работы YANDEX_API_KEY в рамках синтеза текста в речь."

   start_speech("./test/test.wav", text, 'ru', "zahar")