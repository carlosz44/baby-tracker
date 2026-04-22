from django import forms

from .models import Appointment

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 dark:border-zinc-600 "
    "bg-white dark:bg-zinc-700 px-3 py-2 text-slate-700 dark:text-zinc-200 "
    "focus:border-rose-500 focus:ring-rose-500"
)


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["title", "appointment_type", "date", "doctor", "clinic", "notes"]
        labels = {
            "title": "Título",
            "appointment_type": "Tipo de cita",
            "date": "Fecha y hora",
            "doctor": "Doctor/a",
            "clinic": "Clínica",
            "notes": "Notas",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "appointment_type": forms.Select(attrs={"class": INPUT_CLASSES}),
            "date": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local", "class": INPUT_CLASSES}
            ),
            "doctor": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "clinic": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
        }
