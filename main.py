# basic lib imports
from os import path, remove
from time import time

# external lib imports
import argparse

# funcs imports
from src.parser import parse
from src.screen_recorder import start_record, stop_record
from src.browser_engine import start_actions
from src.speech import start_speech, get_wav_duration
from src.video_engine import live_recording_render

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
        video_path = f"{args.output}/{video.metadata.title}.mp4"
        screen_recording_process = start_record(video.metadata, args.output)
        
        # выполнение действий для live recording mode
        # список с парами целых чисел,
        # 1е значение - id сцены (index + 1)
        # 2е значение - время начала сцены
        # 3е - её конец
        # отсчёт идёт в секундах с начала всего ролика
        scene_times = [
            [1, 1, 0]
        ]
        try:
            for i, scene in enumerate(video.scenes):
                start_scene = scene_times[i][-1] + 1
                scene_time = time()
                tts_time = 0
                if scene.tts:
                    tts_path = f"{args.output}/scene_{i + 1}.wav"
                    start_speech(tts_path, scene.tts, video.metadata.language, scene.voice)
                    tts_time = get_wav_duration(tts_path)

                # начала выполнения основных действий
                start_actions(scene.actions, tts_time)

                # добавление таймингов сцены
                end_scene = int(time() - scene_time) + start_scene
                scene_times.append([i + 1, start_scene, end_scene])
        finally:
            # остановка захвата экрана и сохранение
            stop_record(screen_recording_process)
            scene_times.pop(0) # удаление первого элемента сцены, т.к. он по умолчанию и лишний и вырезается
            # потому что это время на запуск браузера

        live_recording_render(args.output, video.metadata.title, scene_times, False)
            
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