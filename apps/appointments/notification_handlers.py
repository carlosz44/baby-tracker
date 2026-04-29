"""Retry handlers for appointment-related notifications.

Imported on app ready() so handlers register themselves with the notifications
registry.
"""
import logging

from apps.notifications.registry import register_handler

from .notification_kinds import (
    ACTION_DELETE,
    ACTION_UPSERT,
    CALENDAR_SYNC_FAILED,
)

logger = logging.getLogger(__name__)


@register_handler(CALENDAR_SYNC_FAILED)
def retry_calendar_sync(notification) -> bool:
    """Re-run sync (or delete) for the appointment+user named in the payload.

    Returns True if the action succeeded (and the notification was resolved
    by mark_resolved inside the calendar service); False otherwise.
    """
    from apps.notifications.models import Notification

    from .models import Appointment
    from .calendar_service import sync_appointment, delete_appointment_events

    payload = notification.payload or {}
    appointment_id = payload.get("appointment_id")
    action = payload.get("action", ACTION_UPSERT)

    if not appointment_id:
        return False

    appointment = Appointment.objects.filter(pk=appointment_id).first()

    if action == ACTION_UPSERT:
        if appointment is None:
            return False
        sync_appointment(appointment)
    elif action == ACTION_DELETE:
        if appointment is not None:
            delete_appointment_events(appointment)
        else:
            return False
    else:
        logger.warning("Unknown action %s in notification %s", action, notification.pk)
        return False

    notification.refresh_from_db()
    return notification.resolved_at is not None
