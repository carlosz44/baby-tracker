from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField("email address", unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class Profile(models.Model):
    """Shared pregnancy profile. Singleton — one row per installation, both
    partners read/write the same record."""

    due_date = models.DateField(
        help_text="First day of last menstrual period (FUR/LMP)",
        null=True,
        blank=True,
    )
    scheduled_birth_at = models.DateTimeField(
        help_text="Scheduled date and time of birth, drives the dashboard countdown",
        null=True,
        blank=True,
    )

    @classmethod
    def get_singleton(cls):
        profile = cls.objects.first()
        if profile is None:
            profile = cls.objects.create()
        return profile

    @property
    def pregnancy_week(self):
        if not self.due_date:
            return None
        delta = timezone.localdate() - self.due_date
        return delta.days // 7

    @property
    def gestational_age(self):
        """Weeks plus days since FUR in clinical notation, e.g. "36+3"."""
        if not self.due_date:
            return None
        weeks, days = divmod((timezone.localdate() - self.due_date).days, 7)
        return f"{weeks}+{days}"

    @property
    def days_remaining(self):
        if not self.due_date:
            return None
        estimated_delivery = self.due_date + timedelta(days=280)
        return (estimated_delivery - timezone.localdate()).days

    @property
    def estimated_delivery_date(self):
        if not self.due_date:
            return None
        return self.due_date + timedelta(days=280)

    @property
    def birth_countdown(self):
        """Time left until the scheduled birth, split for display. Stays at
        zero once the moment has passed."""
        if not self.scheduled_birth_at:
            return None
        remaining = (self.scheduled_birth_at - timezone.now()).total_seconds()
        total_seconds = max(int(remaining), 0)
        days, rest = divmod(total_seconds, 86400)
        hours, rest = divmod(rest, 3600)
        minutes, seconds = divmod(rest, 60)
        return {
            "total_seconds": total_seconds,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
        }

    def __str__(self):
        return f"Pregnancy (due {self.due_date})" if self.due_date else "Pregnancy"
