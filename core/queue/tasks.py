from core.utils.logger import LoggerFactory
from main import process_video

from .celery_app import celery_app

log = LoggerFactory.get_logger(__name__)


@celery_app.task(name="render_video_task")
def render_video_task(file_path: str, output_dir: str) -> dict:
    log.info("Старт queued-задачи: file=%s, output=%s", file_path, output_dir)
    return process_video(file_path, output_dir)
