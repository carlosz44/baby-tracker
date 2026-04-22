from django import forms

from .models import PregnancyFile

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 dark:border-zinc-600 "
    "bg-white dark:bg-zinc-700 px-3 py-2 text-slate-700 dark:text-zinc-200 "
    "focus:border-rose-500 focus:ring-rose-500"
)


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
