"""Notification kinds owned by the appointments app."""

CALENDAR_SYNC_FAILED = "calendar_sync_failed"
CALENDAR_AUTH_REQUIRED = "calendar_auth_required"

ACTION_UPSERT = "upsert"
ACTION_DELETE = "delete"


def sync_dedupe_key(appointment_id: int, user_id: int, action: str) -> str:
    return f"appointment:{appointment_id}:user:{user_id}:{action}"
