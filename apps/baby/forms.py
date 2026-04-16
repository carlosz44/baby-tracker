from django import forms

from .models import BirthPlan, KickCount, WeeklyLog

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 dark:border-slate-600 "
    "bg-white dark:bg-slate-700 px-3 py-2 text-slate-700 dark:text-slate-200 "
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
        widgets = {
            "week_number": forms.NumberInput(attrs={"class": INPUT_CLASSES}),
            "weight_kg": forms.NumberInput(attrs={"class": INPUT_CLASSES, "step": "0.1"}),
            "blood_pressure_systolic": forms.NumberInput(attrs={"class": INPUT_CLASSES, "placeholder": "Systolic"}),
            "blood_pressure_diastolic": forms.NumberInput(attrs={"class": INPUT_CLASSES, "placeholder": "Diastolic"}),
            "symptoms": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
            "mood": forms.Select(attrs={"class": INPUT_CLASSES}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
        }


class KickCountForm(forms.ModelForm):
    class Meta:
        model = KickCount
        fields = ["date", "count", "duration_minutes", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": INPUT_CLASSES}),
            "count": forms.NumberInput(attrs={"class": INPUT_CLASSES}),
            "duration_minutes": forms.NumberInput(attrs={"class": INPUT_CLASSES, "placeholder": "Minutes"}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 2}),
        }


class BirthPlanForm(forms.ModelForm):
    class Meta:
        model = BirthPlan
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": INPUT_CLASSES,
                    "rows": 20,
                    "placeholder": "Write your birth plan here...",
                }
            ),
        }
