import os

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


class PregnancyFile(models.Model):
    CATEGORIES = [
        ("ultrasound", "Ecografía"),
        ("lab_result", "Análisis"),
        ("prescription", "Receta"),
        ("belly_photo", "Foto de barriga"),
        ("other", "Otro"),
    ]

    file = models.FileField(
        upload_to="pregnancy-files/%Y/%m/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp", "pdf"]
            ),
        ],
    )
    category = models.CharField(max_length=20, choices=CATEGORIES)
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="files",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_files",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    @property
    def is_image(self):
        if self.file and self.file.name:
            return self.file.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        return False

    @property
    def is_pdf(self):
        if self.file and self.file.name:
            return self.file.name.lower().endswith(".pdf")
        return False

    @property
    def filename(self):
        if self.file and self.file.name:
            return os.path.basename(self.file.name)
        return ""

    def __str__(self):
        return self.title
