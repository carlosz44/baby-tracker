from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("kind", "title", "severity", "user", "attempts", "resolved_at", "created_at")
    list_filter = ("kind", "severity", "resolved_at")
    search_fields = ("title", "message", "dedupe_key")
    readonly_fields = ("created_at", "updated_at", "last_attempted_at")
