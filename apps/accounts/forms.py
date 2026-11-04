from django import forms

from .models import Profile

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 dark:border-zinc-600 "
    "bg-white dark:bg-zinc-700 px-3 py-2 text-slate-700 dark:text-zinc-200 "
    "focus:border-rose-500 focus:ring-rose-500"
)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["due_date", "scheduled_birth_at"]
        labels = {
            "due_date": "Fecha de la última menstruación (FUR)",
            "scheduled_birth_at": "Fecha y hora programada del parto",
        }
        widgets = {
            "due_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": INPUT_CLASSES},
            ),
            "scheduled_birth_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local", "class": INPUT_CLASSES},
            ),
        }
