from django.contrib import admin

from .models import BirthPlan, KickSession


@admin.register(KickSession)
class KickSessionAdmin(admin.ModelAdmin):
    list_display = ("started_at", "count", "goal_reached", "duration_minutes", "source", "logged_by")
    list_filter = ("source", "goal_reached")
    date_hierarchy = "started_at"


@admin.register(BirthPlan)
class BirthPlanAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
