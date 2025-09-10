from django.db import models
import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model
from admin_app.models import Platform

User = get_user_model()

class Post(models.Model):
    MEDIA_TYPE = [
        ('video', 'Video'),
        ('photo','Photo')
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    Platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    platform_post_id = models.CharField(max_length=128, unique=True)
    media_type = models.CharField(choices=MEDIA_TYPE, max_length=50)
    caption_original = models.TextField(blank=True)
    caption_summary = models.TextField(blank=True, null=True)
    summary_generated = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    platform_comment_id = models.CharField(max_length=128, unique=True)
    parent_comment_id = models.CharField(max_length=200, blank=True, null=True)
    is_reply = models.BooleanField(blank=True, null=True)
    comment = models.TextField()
    tone_integer = models.IntegerField(null=True, blank=True)
    tone_name = models.CharField(max_length=64, null=True, blank=True)
    delete_flag = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)


