# главный файл запуска системы
import sys
import os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import traceback
from os import path
from core.utils.speech import start_speech, get_wav_duration
from engines.live.screen_recorder import start_record, stop_record
from core.parser import parse
from engines.live.video_engine import live_recording_render
from engines.screenshot.screenshot_engine import process_screenshot_video
from time import time

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
            from engines.live.browser_engine import start_actions
            # захват экрана
            screen_recording_process = start_record(video.metadata, args.output)

            # выполнение действий для live recording mode
            # список с парами целых чисел,
            # 1е значение - id сцены (index + 1)
            # 2е значение - время начала сцены
            # 3е - её конец
            # отсчёт идёт в секундах с начала всего ролика
            scene_times = [
                [0, 0, 1] # 1 сцена будет обрезана из-за загрузки браузера
            ]
            try:
                for i, scene in enumerate(video.acts[0].scenes):
                    start_scene = scene_times[i][-1]
                    scene_time = time()
                    tts_time = 0
                    if scene.tts:
                        tts_path = f"{args.output}/scene_{i + 1}.wav"
                        start_speech(tts_path, scene.tts, video.metadata.language, scene.voice)
                        tts_time = get_wav_duration(tts_path)

                    # начало выполнения основных действий
                    start_actions(scene.actions, tts_time)

                    # добавление таймингов сцены
                    end_scene = time() - scene_time + start_scene
                    scene_times.append([i + 1, start_scene, end_scene])
            except Exception as e:
                print(e)
                print("ERROR WAS OCCURED")
                traceback.print_exc()
                return
            finally:
                # остановка захвата экрана и сохранение
                stop_record(screen_recording_process)

            live_recording_render(args.output, video.metadata.title, scene_times, False)
        else:
            print(f"ошибка: неизвестный режим {video.metadata.mode}")

    except Exception as e:
        print(f"произошла критическая ошибка: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()