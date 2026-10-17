from django.conf import settings
from django.db import models
from django.utils import timezone


class WeeklyLog(models.Model):
    MOOD_CHOICES = [
        ("great", "Excelente"),
        ("good", "Bien"),
        ("ok", "Regular"),
        ("bad", "Mal"),
        ("terrible", "Muy mal"),
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


class KickSession(models.Model):
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("screenshot", "Captura"),
        ("counter", "Contador"),
    ]

    started_at = models.DateTimeField(unique=True)
    date = models.DateField(db_index=True, editable=False)
    count = models.PositiveSmallIntegerField()
    target = models.PositiveSmallIntegerField(default=10)
    goal_reached = models.BooleanField(default=False)
    time_to_goal_seconds = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    kick_offsets = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="manual")
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kick_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{timezone.localtime(self.started_at):%Y-%m-%d %H:%M} — {self.count} kicks"

    def save(self, *args, **kwargs):
        self.date = timezone.localdate(self.started_at)
        super().save(*args, **kwargs)

    def set_goal_from_duration(self):
        self.goal_reached = self.count >= self.target
        # With extra kicks past the target, the time to reach it is unknown.
        self.time_to_goal_seconds = self.duration_seconds if self.count == self.target else None

    @property
    def duration_minutes(self):
        if self.duration_seconds is None:
            return None
        return round(self.duration_seconds / 60)


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
