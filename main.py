# basic lib imports
from os import path

from

# external lib imports
import argparse

# funcs imports
from src.parser import parse
from src.screen_recorder import start_record, stop_record
from src.browser_engine import start_actions
from src.speech import start_speech

# кирилл: Импорт движка для работы со скриншотами
from src.screenshot_engine import process_screenshot_video

# добавление аргументов для работы в CLI режиме
parser = argparse.ArgumentParser(description='Система генерации демонстрационных роликов на основе YAML-скриптов.')
parser.add_argument("-f", "--file", help="Путь до YAML-скрипта. Обязательный параметр.")
parser.add_argument("-o", "--output", help="Путь до директории сохранения видео. Обязательный параметр.")

def main():
    args = parser.parse_args()

    # оригинальные проверки вадимки
    assert args.file, "Необходимо указать путь до YAML-скрипта. Параметр -f."
    assert args.output, "Необходимо указать путь до директории сохранения видео. Параметр -o."

    assert path.exists(args.file), "Указанный YAML-скрипт не существует."
    assert args.file.split('.')[-1] in ["yaml", "YAML", "yml", "YML"], "Указанный скрипт не является YAML-форматом."
    assert path.isdir(args.output), "Указанная директория не является таковой."

    # парсинг скрипта (возвращает VideoObject)
    video = parse(args.file)

    # выбор режима записи
    if video.metadata.mode == "live":
        # захват экрана
        screen_recording_process = start_record(video.metadata, args.output)
        
        # выполнение действий для live recording mode
        try:
            for i, scene in enumerate(video.scenes):
                if scene.tts:
                    start_speech(f"{args.output}/scene_{i + 1}.wav", scene.tts, video.metadata.language, scene.voice)
                start_actions(scene.actions)
        finally:
            # остановка захвата экрана и сохранение
            stop_record(screen_recording_process)
            
    elif video.metadata.mode == "screenshot":
        # кирилл: логика Screenshot Mode
        # генерируем видео на основе набора изображений и аннотаций
        print(f">>> Начинаю сборку видео (Screenshot Mode): {video.metadata.title}")
        process_screenshot_video(video, args.output)
        
    else:
        # защита от неправильного ввода, если парсер пропустил значение
        print(f"Ошибка: Режим '{video.metadata.mode}' не поддерживается.")

if __name__ == "__main__":
    main()