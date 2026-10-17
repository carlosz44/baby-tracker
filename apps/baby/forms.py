from datetime import timedelta

from django import forms
from django.utils import timezone

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["duration_minutes"].initial = self.instance.duration_minutes

    def clean_started_at(self):
        started_at = self.cleaned_data["started_at"]
        current = self.instance.started_at
        # The input only shows minutes; keep stored seconds when the minute is unchanged.
        if self.instance.pk and started_at == current.replace(second=0, microsecond=0):
            return current
        return started_at

    def save(self, commit=True):
        session = super().save(commit=False)
        if "duration_minutes" in self.changed_data:
            minutes = self.cleaned_data["duration_minutes"]
            session.duration_seconds = minutes * 60 if minutes else None
        if {"count", "duration_minutes"} & set(self.changed_data):
            # Manual corrections override per-kick times from the counter.
            session.kick_offsets = []
        session.set_goal()
        if commit:
            session.save()
        return session


class KickCounterForm(forms.Form):
    """Validates the JSON payload posted by the in-app counter."""

    started_at = forms.DateTimeField()
    duration_seconds = forms.IntegerField(min_value=0, max_value=24 * 60 * 60)
    kick_offsets = forms.JSONField(required=False)
    notes = forms.CharField(required=False, max_length=1000)

    def clean_started_at(self):
        started_at = self.cleaned_data["started_at"]
        if started_at > timezone.now() + timedelta(minutes=1):
            raise forms.ValidationError("La sesión no puede empezar en el futuro.")
        return started_at

    def clean_kick_offsets(self):
        offsets = self.cleaned_data["kick_offsets"] or []
        valid = isinstance(offsets, list) and len(offsets) <= 1000 and all(
            isinstance(o, (int, float)) and not isinstance(o, bool) and o >= 0 for o in offsets
        )
        if not valid or offsets != sorted(offsets):
            raise forms.ValidationError("Tiempos de pataditas inválidos.")
        return [round(o, 1) for o in offsets]

    def clean(self):
        cleaned = super().clean()
        offsets = cleaned.get("kick_offsets")
        duration = cleaned.get("duration_seconds")
        if offsets is None or duration is None:
            return cleaned
        if offsets and offsets[-1] > duration + 1:
            raise forms.ValidationError("La duración es menor que el tiempo de la última patadita.")
        cleaned["count"] = len(offsets)
        return cleaned


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
