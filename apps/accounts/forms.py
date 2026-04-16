from django import forms

from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["due_date"]
        widgets = {
            "due_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": (
                        "w-full rounded-lg border border-slate-300 dark:border-slate-600 "
                        "bg-white dark:bg-slate-700 px-3 py-2 text-slate-700 dark:text-slate-200 "
                        "focus:border-rose-500 focus:ring-rose-500"
                    ),
                }
            ),
        }
