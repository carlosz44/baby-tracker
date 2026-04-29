from django.conf import settings
from django.db import models


class Notification(models.Model):
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_ERROR, "Error"),
    ]

    kind = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(
        max_length=16, choices=SEVERITY_CHOICES, default=SEVERITY_WARNING
    )
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    dedupe_key = models.CharField(max_length=255, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resolved_at", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.kind}] {self.title}"

    @property
    def is_unresolved(self):
        return self.resolved_at is None
