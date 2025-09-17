from django.contrib import admin
from .models import ToneType, Tone, ToneSetting, Post, Comment


@admin.register(ToneType)
class ToneTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")  # columns in admin list
    search_fields = ("name",)      # search bar


@admin.register(Tone)
class ToneAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    list_filter = ("created_by", "created_at")
    search_fields = ("name", "created_by__username")  # allow searching by tone name or user


@admin.register(ToneSetting)
class ToneSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "tone", "tone_type", "enabled")
    list_filter = ("enabled", "tone", "tone_type")
    search_fields = ("tone__name", "tone_type__name")
    list_editable = ("enabled",)  # allow toggling directly in table

    class Meta:
        verbose_name = "Tone Setting"
        verbose_name_plural = "Tone Settings"

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        'platform_post_id', 'user_id', 'media_type','custom_tone', 
        'summary_generated', 'first_seen_at', 'created_at'
    )
    list_filter = ('media_type', 'summary_generated',)
    search_fields = ('platform_post_id', 'caption_original', 'user_id__username')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        'platform_comment_id', 'post', 'parent_comment_id', 
        'is_reply', 'detected_tone', 'delete_flag', 'processed_at', 'created_at'
    )
    list_filter = ('is_reply', 'delete_flag', 'detected_tone')
    search_fields = ('platform_comment_id', 'comment', 'post__platform_post_id')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
