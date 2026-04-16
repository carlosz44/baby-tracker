from django.conf import settings
from django.db import models


class WeeklyLog(models.Model):
    MOOD_CHOICES = [
        ("great", "Great"),
        ("good", "Good"),
        ("ok", "OK"),
        ("bad", "Bad"),
        ("terrible", "Terrible"),
    ]

    week_number = models.PositiveSmallIntegerField()
    date = models.DateField(auto_now_add=True)
    weight_kg = models.DecimalField(max_digits=4, decimal_places=1)
    blood_pressure_systolic = models.PositiveSmallIntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.PositiveSmallIntegerField(null=True, blank=True)
    symptoms = models.TextField(blank=True)
    mood = models.CharField(max_length=10, choices=MOOD_CHOICES)
    notes = models.TextField(blank=True)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_logs",
    )

    class Meta:
        ordering = ["-date", "-week_number"]

    def __str__(self):
        return f"Week {self.week_number} — {self.date}"


class KickCount(models.Model):
    date = models.DateField()
    count = models.PositiveSmallIntegerField()
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kick_counts",
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} — {self.count} kicks"


class BirthPlan(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="birth_plan",
    )
    content = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Birth plan for {self.user.email}"
