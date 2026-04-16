from django.contrib import admin

from .models import BirthPlan, KickCount, WeeklyLog


@admin.register(WeeklyLog)
class WeeklyLogAdmin(admin.ModelAdmin):
    list_display = ("week_number", "date", "weight_kg", "mood", "logged_by")
    list_filter = ("mood",)


@admin.register(KickCount)
class KickCountAdmin(admin.ModelAdmin):
    list_display = ("date", "count", "duration_minutes", "logged_by")


@admin.register(BirthPlan)
class BirthPlanAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
