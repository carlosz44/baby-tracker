from django.db import models


class Appointment(models.Model):
    APPOINTMENT_TYPES = [
        ("obstetric", "Obstétrica"),
        ("ultrasound", "Ecografía"),
        ("lab", "Análisis"),
        ("nutrition", "Nutrición"),
        ("other", "Otro"),
    ]

    title = models.CharField(max_length=200)
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPES)
    date = models.DateTimeField()
    doctor = models.CharField(max_length=200, blank=True)
    clinic = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    google_calendar_event_ids = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date"]

    @property
    def pregnancy_week_at_appointment(self):
        from apps.accounts.models import Profile

        profile = Profile.objects.first()
        if not profile or not profile.due_date:
            return None
        delta = self.date.date() - profile.due_date
        return delta.days // 7

    def __str__(self):
        return f"{self.title} — {self.date:%Y-%m-%d %H:%M}"
