from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.appointments.calendar_service import (
    MissingCalendarAuth,
    delete_appointment_events,
    sync_appointment,
)
from apps.appointments.models import Appointment
from apps.appointments.notification_kinds import (
    ACTION_DELETE,
    ACTION_UPSERT,
    CALENDAR_AUTH_REQUIRED,
    CALENDAR_SYNC_FAILED,
    sync_dedupe_key,
)
from apps.notifications.models import Notification
from apps.notifications.registry import register_handler
from apps.notifications.services import (
    mark_resolved,
    record_notification,
    retry_notification,
    unresolved_count,
)


# ── services ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_record_notification_creates_row(user):
    n = record_notification(
        kind="test_kind",
        title="hello",
        user=user,
        dedupe_key="k1",
    )
    assert n.pk is not None
    assert n.attempts == 1
    assert n.resolved_at is None


@pytest.mark.django_db
def test_record_notification_dedupes(user):
    n1 = record_notification(kind="t", title="a", dedupe_key="k", user=user)
    n2 = record_notification(kind="t", title="b", dedupe_key="k", user=user)
    assert n1.pk == n2.pk
    assert n2.attempts == 2
    assert Notification.objects.count() == 1
    assert n2.title == "b"


@pytest.mark.django_db
def test_record_notification_creates_new_row_after_resolution(user):
    n1 = record_notification(kind="t", title="a", dedupe_key="k", user=user)
    mark_resolved(dedupe_key="k")
    n2 = record_notification(kind="t", title="b", dedupe_key="k", user=user)
    assert n1.pk != n2.pk
    assert Notification.objects.count() == 2


@pytest.mark.django_db
def test_mark_resolved_only_touches_unresolved(user):
    record_notification(kind="t", title="a", dedupe_key="k", user=user)
    rows = mark_resolved(dedupe_key="k")
    assert rows == 1
    rows = mark_resolved(dedupe_key="k")
    assert rows == 0  # already resolved


@pytest.mark.django_db
def test_retry_notification_runs_handler():
    calls = {"count": 0}

    @register_handler("retry_test_kind")
    def _handler(notification):
        calls["count"] += 1
        return True

    n = record_notification(kind="retry_test_kind", title="x", dedupe_key="rk")
    result = retry_notification(n)
    assert result is True
    assert calls["count"] == 1
    n.refresh_from_db()
    assert n.attempts == 2


@pytest.mark.django_db
def test_retry_without_handler_returns_false():
    n = record_notification(kind="no_handler_kind", title="x", dedupe_key="nh")
    assert retry_notification(n) is False


@pytest.mark.django_db
def test_unresolved_count_filters_per_user(user):
    record_notification(kind="t", title="for-user", user=user, dedupe_key="a")
    record_notification(kind="t", title="for-everyone", user=None, dedupe_key="b")
    other = type(user).objects.create_user(
        username="o", email="o@example.com", password="x"
    )
    record_notification(kind="t", title="for-other", user=other, dedupe_key="c")

    assert unresolved_count(user=user) == 2  # own + for-everyone
    assert unresolved_count(user=other) == 2
    assert unresolved_count() == 3


# ── calendar sync integration ───────────────────────────────────────────────


@pytest.mark.django_db
def test_sync_records_calendar_auth_required_when_missing_refresh_token(user):
    appt = Appointment.objects.create(
        title="Test",
        appointment_type="other",
        date=timezone.now(),
    )

    with patch(
        "apps.appointments.calendar_service.upsert_event_for_user",
        side_effect=MissingCalendarAuth("no_refresh_token"),
    ):
        sync_appointment(appt)

    n = Notification.objects.get(
        dedupe_key=sync_dedupe_key(appt.pk, user.pk, ACTION_UPSERT)
    )
    assert n.kind == CALENDAR_AUTH_REQUIRED
    assert n.severity == Notification.SEVERITY_ERROR
    assert n.payload["reason"] == "no_refresh_token"
    assert n.payload["action"] == ACTION_UPSERT


@pytest.mark.django_db
def test_sync_records_calendar_sync_failed_on_generic_exception(user):
    appt = Appointment.objects.create(
        title="Test",
        appointment_type="other",
        date=timezone.now(),
    )

    with patch(
        "apps.appointments.calendar_service.upsert_event_for_user",
        side_effect=RuntimeError("boom"),
    ):
        sync_appointment(appt)

    n = Notification.objects.get(
        dedupe_key=sync_dedupe_key(appt.pk, user.pk, ACTION_UPSERT)
    )
    assert n.kind == CALENDAR_SYNC_FAILED
    assert n.severity == Notification.SEVERITY_WARNING


@pytest.mark.django_db
def test_sync_resolves_existing_notification_on_success(user):
    appt = Appointment.objects.create(
        title="Test",
        appointment_type="other",
        date=timezone.now(),
    )
    record_notification(
        kind=CALENDAR_SYNC_FAILED,
        title="prior failure",
        dedupe_key=sync_dedupe_key(appt.pk, user.pk, ACTION_UPSERT),
        payload={
            "appointment_id": appt.pk,
            "user_id": user.pk,
            "action": ACTION_UPSERT,
        },
    )

    with patch(
        "apps.appointments.calendar_service.upsert_event_for_user",
        return_value="event-123",
    ):
        sync_appointment(appt)

    assert Notification.objects.filter(resolved_at__isnull=True).count() == 0


@pytest.mark.django_db
def test_retry_handler_resolves_when_underlying_call_succeeds(user):
    # Ensure the handler is registered (apps ready may not have run in test ctx)
    import apps.appointments.notification_handlers  # noqa: F401

    appt = Appointment.objects.create(
        title="Test",
        appointment_type="other",
        date=timezone.now(),
    )
    n = record_notification(
        kind=CALENDAR_SYNC_FAILED,
        title="prior failure",
        dedupe_key=sync_dedupe_key(appt.pk, user.pk, ACTION_UPSERT),
        payload={
            "appointment_id": appt.pk,
            "user_id": user.pk,
            "action": ACTION_UPSERT,
        },
    )

    with patch(
        "apps.appointments.calendar_service.upsert_event_for_user",
        return_value="event-456",
    ):
        result = retry_notification(n)

    assert result is True
    n.refresh_from_db()
    assert n.resolved_at is not None


# ── views ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_notifications_page_renders(client):
    record_notification(kind="t", title="visible", dedupe_key="v")
    response = client.get("/notifications/")
    assert response.status_code == 200
    assert b"visible" in response.content


@pytest.mark.django_db
def test_dismiss_marks_resolved(client):
    n = record_notification(kind="t", title="x", dedupe_key="x")
    response = client.post(f"/notifications/{n.pk}/dismiss/")
    assert response.status_code == 302
    n.refresh_from_db()
    assert n.resolved_at is not None


# ── refresh error classification ────────────────────────────────────────────


def test_classify_refresh_error_invalid_scope():
    from google.auth.exceptions import RefreshError

    from apps.appointments.calendar_service import _classify_refresh_error

    err = RefreshError("invalid_scope: Bad Request", {"error": "invalid_scope"})
    assert _classify_refresh_error(err) == "invalid_scope"


def test_classify_refresh_error_other():
    from google.auth.exceptions import RefreshError

    from apps.appointments.calendar_service import _classify_refresh_error

    err = RefreshError("invalid_grant", {"error": "invalid_grant"})
    assert _classify_refresh_error(err) == "refresh_failed"


@pytest.mark.django_db
def test_resync_future_appointments_only_touches_future(user):
    from datetime import timedelta

    from apps.appointments.calendar_service import resync_future_appointments

    past = Appointment.objects.create(
        title="Past", appointment_type="other",
        date=timezone.now() - timedelta(days=2),
    )
    future_a = Appointment.objects.create(
        title="Future A", appointment_type="other",
        date=timezone.now() + timedelta(days=1),
    )
    future_b = Appointment.objects.create(
        title="Future B", appointment_type="other",
        date=timezone.now() + timedelta(days=7),
    )

    seen = []
    with patch(
        "apps.appointments.calendar_service.upsert_event_for_user",
        side_effect=lambda appt, user, event_id=None: seen.append(appt.pk) or "ev-id",
    ):
        summary = resync_future_appointments()

    assert summary["appointments"] == 2
    assert summary["errors"] == 0
    assert past.pk not in seen
    assert future_a.pk in seen
    assert future_b.pk in seen


def test_auth_required_message_dispatches_by_reason():
    from apps.appointments.calendar_service import auth_required_message

    assert "permiso de Google Calendar" in auth_required_message("invalid_scope")
    assert "refresh token" in auth_required_message("no_refresh_token")
    assert "no ha conectado" in auth_required_message("no_token")
    # Unknown reason falls through to default
    assert auth_required_message("totally_unknown")
