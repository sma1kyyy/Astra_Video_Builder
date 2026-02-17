# главный файл запуска системы
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import traceback
from os import path


from core.parser import parse
from engines.screenshot.screenshot_engine import process_screenshot_video

# настройка аргументов командной строки
parser = argparse.ArgumentParser(description="генерация роликов из yaml скриптов")
parser.add_argument("-f", "--file", help="путь к yaml файлу")
parser.add_argument("-o", "--output", help="директория для сохранения результата")


def main():
    args = parser.parse_args()

    # базовая проверка входных данных
    if not args.file or not args.output:
        print("ошибка: укажите обязательные параметры -f и -o")
        return

    if not path.exists(args.file):
        print(f"ошибка: файл {args.file} не найден")
        return

    if not path.isdir(args.output):
        print(f"ошибка: директория {args.output} не существует")
        return

    # запуск процесса
    try:
        # парсинг превращает yaml в дерево объектов (video -> acts -> scenes)
        print(f"чтение скрипта: {args.file}")
        video = parse(args.file)

        # проверка режима работы
        if video.metadata.mode == "screenshot":
            process_screenshot_video(video, args.output)
        elif video.metadata.mode == "live":
            print("режим live пока находится в разработке под новую структуру актов")
        else:
            print(f"ошибка: неизвестный режим {video.metadata.mode}")

    except Exception as e:
        print(f"произошла критическая ошибка: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()