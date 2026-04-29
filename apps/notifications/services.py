"""Helpers for creating, resolving, and retrying notifications."""
import logging

from django.db.models import Q
from django.utils import timezone

from .models import Notification
from .registry import get_handler

logger = logging.getLogger(__name__)


def record_notification(
    *,
    kind: str,
    title: str,
    message: str = "",
    severity: str = Notification.SEVERITY_WARNING,
    payload: dict | None = None,
    user=None,
    dedupe_key: str = "",
) -> Notification:
    """Create or refresh an unresolved notification.

    If `dedupe_key` is given and an unresolved notification with that key
    already exists, update it (bump attempts, refresh fields) instead of
    creating a duplicate.
    """
    payload = payload or {}

    if dedupe_key:
        existing = Notification.objects.filter(
            dedupe_key=dedupe_key, resolved_at__isnull=True
        ).first()
        if existing:
            existing.kind = kind
            existing.title = title
            existing.message = message
            existing.severity = severity
            existing.payload = payload
            existing.attempts = existing.attempts + 1
            existing.last_attempted_at = timezone.now()
            existing.save()
            return existing

    return Notification.objects.create(
        kind=kind,
        title=title,
        message=message,
        severity=severity,
        payload=payload,
        user=user,
        dedupe_key=dedupe_key,
        attempts=1,
        last_attempted_at=timezone.now(),
    )


def mark_resolved(*, dedupe_key: str) -> int:
    """Mark every unresolved notification with this dedupe_key as resolved.

    Returns the number of rows updated.
    """
    if not dedupe_key:
        return 0
    return Notification.objects.filter(
        dedupe_key=dedupe_key, resolved_at__isnull=True
    ).update(resolved_at=timezone.now())


def retry_notification(notification: Notification) -> bool:
    """Run the registered handler for this notification's kind.

    Returns True if the handler resolved the notification, False otherwise.
    The handler is responsible for any side effects; this function only
    dispatches and updates retry bookkeeping on the notification row.
    """
    handler = get_handler(notification.kind)
    if handler is None:
        logger.warning("No retry handler registered for kind=%s", notification.kind)
        return False

    notification.attempts = notification.attempts + 1
    notification.last_attempted_at = timezone.now()
    notification.save(update_fields=["attempts", "last_attempted_at", "updated_at"])

    try:
        return bool(handler(notification))
    except Exception:
        logger.exception("Retry handler for kind=%s raised", notification.kind)
        return False


def unresolved_count(user=None) -> int:
    qs = Notification.objects.filter(resolved_at__isnull=True)
    if user is not None:
        qs = qs.filter(Q(user__isnull=True) | Q(user=user))
    return qs.count()
