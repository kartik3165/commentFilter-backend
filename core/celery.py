import os
from celery import Celery
from kombu import Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.task_queues = (
    Queue("webhook_post_queue"),
    Queue("meta_post_info_queue"),
    Queue("llm_post_summary_queue"),
    Queue("webhook_comment_queue"),
    Queue("meta_comment_info_queue"),
    Queue("llm_comment_summary_queue"),
    Queue("delete_comment_queue"),
    Queue("db_content_store_queue"),
    Queue("daily_usage_queue"),

)

# app.conf.task_default_queue = 'webhook_post_queue'

app.conf.update(
    task_acks_late = True,
    worker_prefetch_multiplier = 1,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
)

app.autodiscover_tasks()
