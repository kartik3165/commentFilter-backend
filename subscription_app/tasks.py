from celery import shared_task
from django.db import transaction
from django.utils import timezone
import redis
from django.conf import settings
from uuid import UUID
from django.contrib.auth import get_user_model

from auth_app.models import DailyUsage

User = get_user_model()

r = redis.Redis.from_url(settings.REDIS_URL)
BATCH_SIZE = 1000

@shared_task
def flush_daily_comment_usage():
    """
    Flush Redis per-user daily comment usage into DailyUsage table.
    Compatible with your current User/DailyUsage setup.
    """
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="user:*:comments:*", count=BATCH_SIZE)
        if not keys:
            if cursor == 0:
                break
            continue

        # Fetch counts from Redis
        pipe = r.pipeline()
        for key in keys:
            pipe.hget(key, "count")
        counts = pipe.execute()

        usage_data = []
        for key, count_bytes in zip(keys, counts):
            key_str = key.decode()
            parts = key_str.split(":")
            user_id_str = parts[1]
            date_str = parts[3]

            if count_bytes is None:
                continue

            try:
                user_id = UUID(user_id_str)  # works with UUIDs
            except ValueError:
                continue

            try:
                date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            count = int(count_bytes)
            usage_data.append((user_id, date, count))

        if not usage_data:
            r.delete(*keys)
            if cursor == 0:
                break
            continue

        # Bulk fetch existing records
        user_ids = [ud[0] for ud in usage_data]
        dates = [ud[1] for ud in usage_data]
        existing_objs = list(DailyUsage.objects.filter(user_id__in=user_ids, usage_date__in=dates))
        existing_map = {(obj.user_id_id, obj.usage_date): obj for obj in existing_objs}  # Note _id

        to_create = []
        to_update = []

        for user_id, date, count in usage_data:
            key_tuple = (user_id, date)
            if key_tuple in existing_map:
                obj = existing_map[key_tuple]
                obj.comment_used += count
                to_update.append(obj)
            else:
                to_create.append(DailyUsage(user_id_id=user_id, usage_date=date, comment_used=count, photo_summaries_used=0, video_summaries_used=0))

        # Bulk write
        with transaction.atomic():
            if to_update:
                DailyUsage.objects.bulk_update(to_update, ["comment_used"])
            if to_create:
                DailyUsage.objects.bulk_create(to_create)

        # Delete Redis keys
        r.delete(*keys)

        if cursor == 0:
            break

    print("Daily comment usage flushed successfully")
