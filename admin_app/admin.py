from django.contrib import admin
from .models import Platform, DLQTask


@admin.register(Platform)
class nameAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(DLQTask)
class DLQTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task_type",
        "status",
        "retries",
        "max_retries",
        "last_attempt",
        "created_at",
    )
    list_filter = ("status", "task_type", "created_at")
    search_fields = ("id", "task_type")
    readonly_fields = ("created_at", "last_attempt")
    ordering = ("-created_at",)
