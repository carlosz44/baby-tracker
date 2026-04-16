from django.contrib import admin

from .models import PregnancyFile


@admin.register(PregnancyFile)
class PregnancyFileAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "uploaded_by", "uploaded_at")
    list_filter = ("category",)
    search_fields = ("title",)
    raw_id_fields = ("uploaded_by", "appointment")
