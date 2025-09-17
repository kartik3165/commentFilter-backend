from django.conf import settings
from django.db import models
import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class ToneType(models.Model):
    serialNo = models.IntegerField(max_length=5, null=True, default=True)
    name = models.CharField(max_length=200) # vulgar, Flirty, Negative, spam

    def __str__(self):
        return self.name

class Tone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150) # Default tone or strict tone
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tones')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class ToneSetting(models.Model):
    tone = models.ForeignKey('moderator_app.Tone', on_delete=models.CASCADE, related_name='settings')
    tone_type = models.ForeignKey('moderator_app.ToneType', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    class Meta:
        unique_together = ('tone', 'tone_type')

    def __str__(self):
        return self.tone.name


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    platform_post_id = models.CharField(max_length=128, unique=True, null=True)
    media_type = models.CharField(max_length=50, null=True)
    media_url = models.JSONField(null=True, blank=True)
    caption_original = models.TextField(blank=True)
    caption_summary = models.TextField(blank=True, null=True)
    summary_generated = models.BooleanField(default=False, null=True)
    custom_tone = models.ForeignKey('moderator_app.Tone', on_delete=models.SET_NULL, null=True, blank=True, related_name='custom_for_posts')
    first_seen_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)



class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments", null=True)
    platform_comment_id = models.CharField(max_length=128, unique=True, blank=True, null=True)
    parent_comment_id = models.CharField(max_length=200, blank=True, null=True)
    is_reply = models.BooleanField(null=True)
    comment = models.TextField(blank=True, null=True)
    author = models.CharField(null=True,blank=True, max_length=150)
    tone_integer = models.IntegerField(null=True, blank=True)
    detected_tone = models.CharField(max_length=64, null=True, blank=True)
    delete_flag = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)






