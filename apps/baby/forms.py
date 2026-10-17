from django import forms

from .models import BirthPlan, KickSession, WeeklyLog

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 dark:border-zinc-600 "
    "bg-white dark:bg-zinc-700 px-3 py-2 text-slate-700 dark:text-zinc-200 "
    "focus:border-rose-500 focus:ring-rose-500"
)


class WeeklyLogForm(forms.ModelForm):
    class Meta:
        model = WeeklyLog
        fields = [
            "week_number",
            "weight_kg",
            "blood_pressure_systolic",
            "blood_pressure_diastolic",
            "symptoms",
            "mood",
            "notes",
        ]
        labels = {
            "week_number": "Semana",
            "weight_kg": "Peso (kg)",
            "blood_pressure_systolic": "Presión sistólica",
            "blood_pressure_diastolic": "Presión diastólica",
            "symptoms": "Síntomas",
            "mood": "Estado de ánimo",
            "notes": "Notas",
        }
        widgets = {
            "week_number": forms.NumberInput(attrs={"class": INPUT_CLASSES}),
            "weight_kg": forms.NumberInput(attrs={"class": INPUT_CLASSES, "step": "0.1"}),
            "blood_pressure_systolic": forms.NumberInput(attrs={"class": INPUT_CLASSES, "placeholder": "Sistólica"}),
            "blood_pressure_diastolic": forms.NumberInput(attrs={"class": INPUT_CLASSES, "placeholder": "Diastólica"}),
            "symptoms": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
            "mood": forms.Select(attrs={"class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
        }


class KickSessionForm(forms.ModelForm):
    duration_minutes = forms.IntegerField(
        label="Duración (minutos)",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": INPUT_CLASSES, "placeholder": "Minutos"}),
    )

    class Meta:
        model = KickSession
        fields = ["started_at", "count", "duration_minutes", "notes"]
        labels = {
            "started_at": "Inicio",
            "count": "Número de pataditas",
            "notes": "Notas",
        }
        widgets = {
            "started_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local", "class": INPUT_CLASSES}
            ),
            "count": forms.NumberInput(attrs={"class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 2}),
        }
        error_messages = {
            "started_at": {"unique": "Ya existe una sesión que empezó a esa hora."},
        }

    def save(self, commit=True):
        session = super().save(commit=False)
        minutes = self.cleaned_data.get("duration_minutes")
        session.duration_seconds = minutes * 60 if minutes else None
        session.set_goal_from_duration()
        if commit:
            session.save()
        return session


class BirthPlanForm(forms.ModelForm):
    class Meta:
        model = BirthPlan
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": INPUT_CLASSES,
                    "rows": 20,
                    "placeholder": "Escribe aquí tu plan de parto...",
                }
            ),
        }
