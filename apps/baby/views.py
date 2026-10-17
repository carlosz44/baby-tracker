import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Profile

from .analytics import RANGES, build_report
from .forms import BirthPlanForm, KickCounterForm, KickSessionForm, WeeklyLogForm
from .models import BirthPlan, KickSession, WeeklyLog
from .services import upsert_sessions


@login_required
def weekly_log_list(request):
    logs = WeeklyLog.objects.all()
    return render(request, "baby/log_list.html", {"logs": logs})


@login_required
def weekly_log_create(request):
    profile = Profile.objects.first()
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
    today_sessions = KickSession.objects.filter(date=timezone.localdate())
    return render(request, "baby/kick_counter.html", {"today_sessions": today_sessions})


@login_required
def kick_history(request):
    since = timezone.localdate() - timedelta(days=30)
    recent_sessions = KickSession.objects.filter(date__gte=since)

    if request.method == "POST":
        form = KickSessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.logged_by = request.user
            session.save()
            messages.success(request, "Pataditas registradas.")
            return redirect("kick_history")
    else:
        now = timezone.localtime().replace(second=0, microsecond=0)
        form = KickSessionForm(initial={"started_at": now, "count": 10})

    return render(request, "baby/kick_history.html", {"form": form, "recent_sessions": recent_sessions})


@login_required
def kick_stats(request):
    range_key = request.GET.get("range", "30")
    if range_key not in RANGES:
        range_key = "30"
    profile = Profile.objects.first()
    report = build_report(
        KickSession.objects.order_by("started_at"),
        now=timezone.now(),
        lmp=profile.due_date if profile else None,
        days=RANGES[range_key],
    )
    context = {
        "report": report,
        "range_key": range_key,
        "range_options": [("14", "14 días"), ("30", "30 días"), ("all", "Todo")],
        "weekday_names": "LMXJVSD",
        "level_legend": [(0, "0"), (1, "1"), (2, "2"), (3, "3+")],
    }
    return render(request, "baby/kick_stats.html", context)


@login_required
@require_POST
def kick_session_save(request):
    try:
        payload = json.loads(request.body)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Datos inválidos."}, status=400)

    form = KickCounterForm(payload)
    if not form.is_valid():
        message = next(iter(form.errors.values()))[0]
        return JsonResponse({"error": message}, status=400)

    result = upsert_sessions([form.cleaned_data], source="counter", logged_by=request.user)
    if result.conflicts:
        return JsonResponse({"error": "Ya existe otra sesión con esa hora de inicio."}, status=409)
    if result.created:
        messages.success(request, "Sesión guardada.")
    return JsonResponse({"ok": True})


@login_required
def kick_session_edit(request, pk):
    session = get_object_or_404(KickSession, pk=pk)
    if request.method == "POST":
        form = KickSessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, "Sesión actualizada.")
            return redirect("kick_history")
    else:
        form = KickSessionForm(instance=session)
    return render(request, "baby/kick_session_form.html", {"form": form, "session": session})


@login_required
@require_POST
def kick_session_delete(request, pk):
    get_object_or_404(KickSession, pk=pk).delete()
    messages.success(request, "Sesión eliminada.")
    return redirect("kick_history")


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
