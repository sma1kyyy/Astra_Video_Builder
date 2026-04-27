from celery import Celery

from core.config import settings

celery_app = Celery(
    "aa_video_builder",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["core.queue"])
