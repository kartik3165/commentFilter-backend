from django.contrib import admin
from .models import Post, Comment

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        'platform_post_id', 'user_id', 'media_type', 
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
        'is_reply', 'tone_name', 'delete_flag', 'processed_at', 'created_at'
    )
    list_filter = ('is_reply', 'delete_flag', 'tone_name')
    search_fields = ('platform_comment_id', 'comment', 'post__platform_post_id')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
