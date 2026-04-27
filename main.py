#!/usr/bin/env python3
import argparse
import sys
from os import path
from time import time

from core.parser import parse
from core.utils.logger import LoggerFactory

log = LoggerFactory.get_logger(__name__)

cli = argparse.ArgumentParser(description="Генерация роликов из YAML-скриптов")
cli.add_argument("-f", "--file", required=False, help="путь к yaml файлу")
cli.add_argument("-o", "--output", required=True, help="каталог для сохранения результата")
cli.add_argument(
    "--queue",
    action="store_true",
    help="Поставить задачу в Celery/Redis очередь вместо немедленного запуска",
)
cli.add_argument(
    "--wait",
    action="store_true",
    help="Дождаться завершения queued-задачи и вернуть код результата",
)
cli.add_argument(
    "--task-id",
    help="Проверить статус существующей queued-задачи по task id",
)
cli.add_argument(
    "--timeout",
    type=int,
    default=3600,
    help="Таймаут ожидания queued-задачи в секундах (по умолчанию: 3600)",
)



def _validate_args(args) -> bool:
    if args.task_id:
        return True

    if not args.file:
        log.error("Нужно передать --file, если не используется --task-id")
        return False
    
    if not path.exists(args.file):
        log.error("Файл %s не найден", args.file)
        return False
    if not path.isdir(args.output):
        log.error("Каталог %s не существует", args.output)        
        return False
    return True


def _run_screenshot_mode(video, output_dir: str) -> str:
    from engines.screenshot.screenshot_engine import process_screenshot_video
    #process_screenshot_video(video, output_dir)
    return process_screenshot_video(video, output_dir)


def _run_live_mode(video, output_dir: str) -> str | None:
    from time import sleep

    from core.utils.speech import get_wav_duration, start_speech
    from engines.live.browser_engine import get_driver, quit_driver, start_actions
    from engines.live.screen_recorder import get_recording_diagnostics
    from engines.live.screen_recorder import start_record, stop_record
    from engines.live.video_engine import live_recording_render

    screen_recording_process = None
    scene_times: list = []
    render_attempted = False
    final_path = None

    try:
        driver = get_driver(video.metadata.browser)

        first_scene = video.acts[0].scenes[0]
        if not first_scene.actions or first_scene.actions[0].type != "navigate":
            raise ValueError(
                "Первое действие первой сцены должно быть `navigate` — "
                "иначе нет страницы, на которой выполнять действия."
            )

        first_action = first_scene.actions.pop(0)
        driver.get(first_action.url)

        tts_durations: dict[int, float] = {}
        for i, scene in enumerate(video.acts[0].scenes):
            if scene.tts:
                scene_id = i + 1
                tts_path = f"{output_dir}/scene_{scene_id}.wav"
                start_speech(tts_path, scene.tts, video.metadata.language, scene.voice)
                tts_durations[scene_id] = get_wav_duration(tts_path)

        screen_recording_process = start_record(video.metadata, output_dir)
        sleep(0.3)

        timeline_start = time()
        for i, scene in enumerate(video.acts[0].scenes):
            scene_id = i + 1
            start_scene = time() - timeline_start
            scene_start_time = time()
            tts_time = tts_durations.get(scene_id, 0.0)

            start_actions(scene.actions, tts_time)

            end_scene = time() - scene_start_time + start_scene
            scene_times.append([scene_id, start_scene, end_scene])
    except Exception:
        log.exception("Ошибка во время выполнения live-сценария")
    finally:
        stop_record(screen_recording_process)
        quit_driver()

        if len(scene_times) > 0:
            render_attempted = True
            try:
                final_path = live_recording_render(
                    output_dir,
                    video.metadata.title,
                    scene_times,
                    save_files=video.metadata.save_files,
                )
                log.info("Видео успешно сохранено: %s", final_path)
            except FileNotFoundError as exc:
                diag = get_recording_diagnostics(video.metadata, output_dir)
                log.error("Live render: не найден файл записи экрана: %s", exc)
                log.error(
                    "Диагностика записи: platform=%s, session=%s, backend=%s, input=%s",
                    diag["platform"], diag["session_type"], diag["backend"], diag["input_device"]
                )
                log.error("Ожидаемый файл: %s", diag["expected_record_path"])
                log.error("Команда записи: %s", diag["command"])
            except Exception:
                log.exception("Не удалось смонтировать итоговое видео")

        if not render_attempted:
            log.error("Рендер не был запущен: нет валидных сцен.")

    return final_path


def process_video(file_path: str, output_dir: str) -> dict:
    log.info("Чтение скрипта: %s", file_path)
    video = parse(file_path)

    match video.metadata.mode:
        case "screenshot":
            output_file = _run_screenshot_mode(video, output_dir)
        case "live":
            output_file = _run_live_mode(video, output_dir)
        case other:
            log.error("Неизвестный режим: %s", other)
            raise ValueError(f"Неизвестный режим: {other}")

    return {
        "status": "success",
        "mode": video.metadata.mode,
        "output_file": output_file,
    }


def _check_task_status(task_id: str) -> int:
    from core.queue.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    log.info("Task %s state: %s", task_id, result.state)

    if result.ready():
        if result.successful():
            log.info("Task result: %s", result.result)
            return 0
        log.error("Task failed: %s", result.result)
        return 1

    return 0


def _enqueue_video(args) -> int:
    from core.queue.tasks import render_video_task

    task = render_video_task.delay(args.file, args.output)
    log.info("Задача поставлена в очередь. task_id=%s", task.id)

    if not args.wait:
        return 0

    log.info("Ожидание завершения task_id=%s (timeout=%ss)", task.id, args.timeout)
    try:
        result = task.get(timeout=args.timeout)
        log.info("Задача завершена успешно: %s", result)
        return 0
    except Exception:
        log.exception("Ошибка queued-задачи task_id=%s", task.id)
        return 1

def main() -> int:
    args = cli.parse_args()
    if not _validate_args(args):
        return 2
    
    if args.task_id:
        return _check_task_status(args.task_id)

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
        if args.queue:
            return _enqueue_video(args)

        process_video(args.file, args.output)
        
    except Exception:
        log.exception("Критическая ошибка")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
