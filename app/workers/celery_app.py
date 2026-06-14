"""
Celery application configuration and background tasks.

Usage:
    Start worker: celery -A app.workers.celery_app worker --loglevel=info
    Start beat:   celery -A app.workers.celery_app beat --loglevel=info
"""
import logging
from celery import Celery
from celery.schedules import crontab

from app.configs.settings import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "memcore",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Beat schedule for periodic tasks
    beat_schedule={
        "cleanup-expired-memories": {
            "task": "app.workers.tasks.cleanup_expired_memories",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        },
        "cleanup-expired-tokens": {
            "task": "app.workers.tasks.cleanup_expired_tokens",
            "schedule": crontab(minute=30, hour="*/12"),  # Every 12 hours
        },
    },
)
