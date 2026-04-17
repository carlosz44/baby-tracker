from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Profile

from .forms import BirthPlanForm, KickCountForm, WeeklyLogForm
from .models import BirthPlan, KickCount, WeeklyLog


@login_required
def weekly_log_list(request):
    logs = WeeklyLog.objects.all()
    return render(request, "baby/log_list.html", {"logs": logs})


@login_required
def weekly_log_create(request):
    profile = Profile.objects.filter(user=request.user).first()
    initial = {}
    if profile and profile.pregnancy_week is not None:
        initial["week_number"] = profile.pregnancy_week

    if request.method == "POST":
        form = WeeklyLogForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.logged_by = request.user
            log.save()
            messages.success(request, "Registro semanal guardado.")
            return redirect("weekly_log_list")
    else:
        form = WeeklyLogForm(initial=initial)

    return render(request, "baby/log_form.html", {"form": form})


@login_required
def kick_counter(request):
    seven_days_ago = timezone.now().date() - timedelta(days=7)
    recent_kicks = KickCount.objects.filter(date__gte=seven_days_ago)

    if request.method == "POST":
        form = KickCountForm(request.POST)
        if form.is_valid():
            kick = form.save(commit=False)
            kick.logged_by = request.user
            kick.save()
            messages.success(request, "Pataditas registradas.")
            return redirect("kick_counter")
    else:
        form = KickCountForm(initial={"date": timezone.now().date()})

    return render(request, "baby/kick_counter.html", {"form": form, "recent_kicks": recent_kicks})


@login_required
def birth_plan(request):
    plan, created = BirthPlan.objects.get_or_create(
        user=request.user,
        defaults={"content": ""},
    )

    if request.method == "POST":
        form = BirthPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan de parto guardado.")
            return redirect("birth_plan")
    else:
        form = BirthPlanForm(instance=plan)

    return render(request, "baby/birth_plan.html", {"form": form, "plan": plan})
