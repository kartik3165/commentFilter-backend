from django.contrib import admin
from .models import Social_account

@admin.register(Social_account)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_id",
        "platform",
        "platform_account_id",
        "username",
        "status",
        "linked_at",
        "unlinked_at",
    )
    list_filter = ("platform", "status", "linked_at", "unlinked_at")
    search_fields = ("platform_account_id", "username", "user_id__username", "user_id__email")
    readonly_fields = ("linked_at", "unlinked_at")
    ordering = ("-linked_at",)
