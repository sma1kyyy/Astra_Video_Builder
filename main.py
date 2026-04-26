#!/usr/bin/env python3
import argparse
import sys
from os import path
from time import time

from core.parser import parse
from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)

cli = argparse.ArgumentParser(description="Генерация роликов из YAML-скриптов")
cli.add_argument("-f", "--file", required=True, help="путь к yaml файлу")
cli.add_argument("-o", "--output", required=True, help="директория для сохранения результата")


def _validate_args(args) -> bool:
    if not path.exists(args.file):
        log.error("Файл %s не найден", args.file)
        return False
    if not path.isdir(args.output):
        log.error("Директория %s не существует", args.output)
        return False
    return True


def _run_screenshot_mode(video, output_dir: str) -> None:
    from engines.screenshot.screenshot_engine import process_screenshot_video
    process_screenshot_video(video, output_dir)


def _run_live_mode(video, output_dir: str) -> None:
    from core.utils.speech import get_wav_duration, start_speech
    from engines.live.browser_engine import get_driver, quit_driver, start_actions
    from engines.live.screen_recorder import start_record, stop_record
    from engines.live.video_engine import live_recording_render

    screen_recording_process = None
    scene_times: list = []
    render_attempted = False

    try:
        screen_recording_process = start_record(video.metadata, output_dir)

        warmup_start = time()
        driver = get_driver()
        warmup_end = time() - warmup_start
        log.info("Browser warmup занял %.2fs", warmup_end)
        scene_times.append([0, 0.0, warmup_end])

        for i, scene in enumerate(video.acts[0].scenes):
            scene_id = i + 1
            start_scene = scene_times[-1][2]
            scene_start_time = time()
            tts_time = 0.0

            if scene.tts:
                tts_path = f"{output_dir}/scene_{scene_id}.wav"
                start_speech(tts_path, scene.tts, video.metadata.language, scene.voice)
                tts_time = get_wav_duration(tts_path)

            start_actions(scene.actions, tts_time)

            end_scene = time() - scene_start_time + start_scene
            scene_times.append([scene_id, start_scene, end_scene])
    except Exception:
        log.exception("Ошибка во время выполнения live-сценария")
    finally:
        stop_record(screen_recording_process)
        quit_driver()

        if len(scene_times) > 1:
            render_attempted = True
            try:
                final_path = live_recording_render(
                    output_dir,
                    video.metadata.title,
                    scene_times,
                    save_files=video.metadata.save_files,
                )
                log.info("Видео успешно сохранено: %s", final_path)
            except Exception:
                log.exception("Не удалось смонтировать итоговое видео")

        if not render_attempted:
            log.error("Рендер не был запущен: нет валидных сцен.")


def main() -> int:
    args = cli.parse_args()
    if not _validate_args(args):
        return 2

    try:
        log.info("Чтение скрипта: %s", args.file)
        video = parse(args.file)

        match video.metadata.mode:
            case "screenshot":
                _run_screenshot_mode(video, args.output)
            case "live":
                _run_live_mode(video, args.output)
            case other:
                log.error("Неизвестный режим: %s", other)
                return 2
    except Exception:
        log.exception("Критическая ошибка")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
