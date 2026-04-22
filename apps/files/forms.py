from django import forms
from django.core.exceptions import ValidationError

from .models import PregnancyFile

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 dark:border-zinc-600 "
    "bg-white dark:bg-zinc-700 px-3 py-2 text-slate-700 dark:text-zinc-200 "
    "focus:border-rose-500 focus:ring-rose-500"
)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB (matches Nginx client_max_body_size)


class PregnancyFileForm(forms.ModelForm):
    class Meta:
        model = PregnancyFile
        fields = ["file", "category", "title", "notes", "appointment"]
        labels = {
            "file": "Archivo",
            "category": "Categoría",
            "title": "Título",
            "notes": "Notas",
            "appointment": "Cita relacionada",
        }
        widgets = {
            "file": forms.ClearableFileInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "accept": "image/jpeg,image/png,image/webp,application/pdf",
                }
            ),
            "category": forms.Select(attrs={"class": INPUT_CLASSES}),
            "title": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
            "appointment": forms.Select(attrs={"class": INPUT_CLASSES}),
        }

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > MAX_UPLOAD_SIZE:
            raise ValidationError(
                f"El archivo supera el tamaño máximo de {MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
            )
        return f
