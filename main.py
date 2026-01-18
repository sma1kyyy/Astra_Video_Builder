# basic lib imports
from os import path

# external lib imports
import argparse

# funcs imports
from src.parser import parse
from src.screen_recorder import start_record, stop_record
from src.browser_engine import start_actions

# добавление аргументов для работы в CLI режиме
parser = argparse.ArgumentParser(description='Система генерации демонстрационных роликов на основе YAML-скриптов.')
parser.add_argument("-f", "--file", help="Путь до YAML-скрипта. Обязательный параметр.")
parser.add_argument("-o", "--output", help="Путь до директории сохранения видео. Обязательный параметр.")

def main():
    args = parser.parse_args()

    assert args.file, "Необходимо указать путь до YAML-скрипта. Параметр -f."
    assert args.output, "Необходимо указать путь до директории сохранения видео. Параметр -o."

    assert path.exists(args.file), "Указанный YAML-скрипт не существует."
    assert args.file.split('.')[-1] in ["yaml", "YAML"], "Указанный скрипт не является YAML-форматом."
    assert path.isdir(args.output), "Указанная директория не является таковой."

    # парсинг скрипта
    video = parse(args.file)

    if video.metadata.mode == "live":
        # захват экрана
        screen_recording_process = start_record(video.metadata, args.output)
        # выполнение действий для live recording mode
        for scene in video.scenes:
            start_actions(scene.actions)
        
        # остановка захвата экрана и сохранение
        stop_record(screen_recording_process)
    else:
        pass
        # для кирюши


if __name__ == "__main__":
    main()