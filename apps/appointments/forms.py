from django import forms

from .models import Appointment

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 dark:border-slate-600 "
    "bg-white dark:bg-slate-700 px-3 py-2 text-slate-700 dark:text-slate-200 "
    "focus:border-rose-500 focus:ring-rose-500"
)


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["title", "appointment_type", "date", "doctor", "clinic", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "appointment_type": forms.Select(attrs={"class": INPUT_CLASSES}),
            "date": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": INPUT_CLASSES}
            ),
            "doctor": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "clinic": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
        }
