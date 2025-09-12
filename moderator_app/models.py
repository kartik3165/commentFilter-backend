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
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, null=True)
    platform_post_id = models.CharField(max_length=128, unique=True, null=True)
    media_type = models.CharField(choices=MEDIA_TYPE, max_length=50, null=True)
    media_url = models.JSONField(null=True, blank=True)
    caption_original = models.TextField(blank=True)
    caption_summary = models.TextField(blank=True, null=True)
    summary_generated = models.BooleanField(default=False, null=True)
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





import requests
import json
import re
from django.shortcuts import get_object_or_404

def extract_summary(content: str) -> str:
    """Extract text inside { } if present."""
    match = re.search(r"\{(.*?)\}", content)
    if match:
        return match.group(1).strip()
    return content.strip()

def generate_Summary(self, media_id):
    try:
        post = get_object_or_404(Post, platform_post_id=media_id)

        url = "http://localhost:11434/api/chat"  # change if Docker mapped differently
        payload = {
            "model": "mistral",  # or llama2, qwen, etc.
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f'Summarize "{post.caption_original}" into exactly 8 words '
                        f'for a {post.media_type} on {post.platform}. '
                        f'Return only eight word summary with this {{}} bracket.'
                    )
                }
            ],
            "stream": False
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        # Extract raw content from Ollama
        content = data["message"]["content"]

        # Get clean summary (inside {})
        summary = extract_summary(content)
        return summary

    except requests.RequestException as e:
        raise self.retry(exc=e)
    except Exception as e:
        return self.retry(exc=e)
