from datetime import timedelta

from django.conf import settings
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
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    due_date = models.DateField(
        help_text="First day of last menstrual period (FUR/LMP)",
        null=True,
        blank=True,
    )

    @property
    def pregnancy_week(self):
        if not self.due_date:
            return None
        delta = timezone.now().date() - self.due_date
        return delta.days // 7

    @property
    def days_remaining(self):
        if not self.due_date:
            return None
        estimated_delivery = self.due_date + timedelta(days=280)
        return (estimated_delivery - timezone.now().date()).days

    @property
    def estimated_delivery_date(self):
        if not self.due_date:
            return None
        return self.due_date + timedelta(days=280)

    def __str__(self):
        return f"Profile for {self.user.email}"
