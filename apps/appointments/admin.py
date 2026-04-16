from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("title", "appointment_type", "date", "doctor", "clinic")
    list_filter = ("appointment_type",)
    search_fields = ("title", "doctor", "clinic")
