from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.appointments.calendar_service import (
    resync_future_appointments,
    run_calendar_diagnostics,
)

from .models import Notification
from .registry import has_handler
from .services import retry_notification


def _annotate(notifications):
    for n in notifications:
        n.has_retry = has_handler(n.kind)
    return notifications


@login_required
def notification_list(request):
    unresolved = list(
        Notification.objects.filter(resolved_at__isnull=True).select_related("user")
    )
    resolved = list(
        Notification.objects.filter(resolved_at__isnull=False)
        .select_related("user")
        .order_by("-resolved_at")[:20]
    )
    context = {
        "unresolved": _annotate(unresolved),
        "resolved": _annotate(resolved),
    }
    return render(request, "notifications/list.html", context)


@login_required
@require_POST
def notification_retry(request, pk):
    notification = get_object_or_404(Notification, pk=pk)

    if notification.resolved_at is not None:
        if request.htmx:
            return render(
                request,
                "notifications/_row.html",
                {"n": _annotate([notification])[0], "flash": "already_resolved"},
            )
        messages.info(request, "Esta notificación ya estaba resuelta.")
        return redirect("notification_list")

    if not has_handler(notification.kind):
        flash = "no_handler"
        success = False
    else:
        success = retry_notification(notification)
        flash = "success" if success else "failed"

    notification.refresh_from_db()
    if request.htmx:
        return render(
            request,
            "notifications/_row.html",
            {"n": _annotate([notification])[0], "flash": flash},
        )

    if success:
        messages.success(request, "Reintento correcto.")
    else:
        messages.error(request, "El reintento falló.")
    return redirect("notification_list")


@login_required
def notification_diagnostics(request):
    results = run_calendar_diagnostics()
    return render(
        request, "notifications/_diagnostics.html", {"results": results}
    )


@login_required
@require_POST
def notification_resync(request):
    summary = resync_future_appointments()
    return render(
        request, "notifications/_resync_result.html", {"summary": summary}
    )


@login_required
@require_POST
def notification_dismiss(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    if notification.resolved_at is None:
        notification.resolved_at = timezone.now()
        notification.save(update_fields=["resolved_at", "updated_at"])

    if request.htmx:
        return HttpResponse("")

    messages.success(request, "Notificación descartada.")
    return redirect("notification_list")
