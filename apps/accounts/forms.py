from django import forms

from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["due_date"]
        labels = {"due_date": "Fecha de la última menstruación (FUR)"}
        widgets = {
            "due_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                    "class": (
                        "w-full rounded-lg border border-slate-300 dark:border-zinc-600 "
                        "bg-white dark:bg-zinc-700 px-3 py-2 text-slate-700 dark:text-zinc-200 "
                        "focus:border-rose-500 focus:ring-rose-500"
                    ),
                }
            ),
        }
