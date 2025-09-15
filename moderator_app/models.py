from django.db import models
import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model
from admin_app.models import Platform

User = get_user_model()

class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    platform_post_id = models.CharField(max_length=128, unique=True, null=True)
    media_type = models.CharField(max_length=50, null=True)
    media_url = models.JSONField(null=True, blank=True)
    caption_original = models.TextField(blank=True)
    caption_summary = models.TextField(blank=True, null=True)
    summary_generated = models.BooleanField(default=False, null=True)
    first_seen_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments", null=True)
    platform_comment_id = models.CharField(max_length=128, unique=True, blank=True, null=True)
    parent_comment_id = models.CharField(max_length=200, blank=True, null=True)
    is_reply = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)
    author = models.CharField(null=True,blank=True, max_length=150)
    tone_integer = models.IntegerField(null=True, blank=True)
    tone_name = models.CharField(max_length=64, null=True, blank=True)
    delete_flag = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)




