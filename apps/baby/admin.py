from django.contrib import admin

from .models import BirthPlan, KickSession, WeeklyLog


@admin.register(WeeklyLog)
class WeeklyLogAdmin(admin.ModelAdmin):
    list_display = ("week_number", "date", "weight_kg", "mood", "logged_by")
    list_filter = ("mood",)


@admin.register(KickSession)
class KickSessionAdmin(admin.ModelAdmin):
    list_display = ("started_at", "count", "goal_reached", "duration_minutes", "source", "logged_by")
    list_filter = ("source", "goal_reached")
    date_hierarchy = "started_at"


@admin.register(BirthPlan)
class BirthPlanAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
