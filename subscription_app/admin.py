from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Plan, Subscription

# ---------------- Plan Admin ----------------
@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "price", "comment_limit", "created_at", "updated_at")
    list_display_links = ("id",)  # make ID clickable
    search_fields = ("id",)
    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)


# ---------------- Subscription Admin ----------------
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "plan_id", "start_date", "end_date", "created_at", "updated_at")
    list_display_links = ("id",)
    search_fields = ("id", "user_id__mobile", "plan_id__id")  # search by user mobile or plan id
    list_filter = ("start_date", "end_date", "created_at", "updated_at")
    ordering = ("-created_at",)
