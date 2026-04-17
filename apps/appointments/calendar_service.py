import logging
from datetime import timedelta

from django.conf import settings

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from allauth.socialaccount.models import SocialApp, SocialToken

logger = logging.getLogger(__name__)


def _get_oauth_app():
    app = SocialApp.objects.filter(provider="google").first()
    if app:
        return app.client_id, app.secret
    google_cfg = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
    return google_cfg.get("client_id", ""), google_cfg.get("secret", "")


def get_calendar_service(user):
    token = SocialToken.objects.filter(
        account__user=user,
        account__provider="google",
    ).first()
    if not token:
        logger.warning("No Google token for user %s", user.email)
        return None

    client_id, client_secret = _get_oauth_app()
    credentials = Credentials(
        token=token.token,
        refresh_token=token.token_secret,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _build_event_body(appointment):
    end_time = appointment.date + timedelta(hours=1)
    body = {
        "summary": appointment.title,
        "description": appointment.notes or "",
        "start": {"dateTime": appointment.date.isoformat(), "timeZone": "America/Lima"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Lima"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60},
                {"method": "popup", "minutes": 1440},
            ],
        },
    }
    if appointment.clinic:
        body["location"] = appointment.clinic
    return body


def upsert_event_for_user(appointment, user, event_id=None):
    """Create or update the appointment on user's primary calendar. Returns event id or None."""
    service = get_calendar_service(user)
    if not service:
        return None

    body = _build_event_body(appointment)

    try:
        if event_id:
            event = service.events().update(
                calendarId="primary", eventId=event_id, body=body
            ).execute()
        else:
            event = service.events().insert(calendarId="primary", body=body).execute()
        return event.get("id")
    except HttpError as e:
        if event_id and e.resp.status in (404, 410):
            event = service.events().insert(calendarId="primary", body=body).execute()
            return event.get("id")
        logger.exception("Calendar upsert failed for user %s", user.email)
        return None


def delete_event_for_user(user, event_id):
    service = get_calendar_service(user)
    if not service:
        return
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status in (404, 410):
            logger.info("Event %s already gone for user %s", event_id, user.email)
        else:
            raise


def sync_appointment(appointment):
    """Create or update event on every user's calendar that has Google linked."""
    from apps.accounts.models import User

    event_ids = dict(appointment.google_calendar_event_ids or {})
    changed = False

    for user in User.objects.all():
        existing = event_ids.get(str(user.pk))
        new_id = upsert_event_for_user(appointment, user, event_id=existing)
        if new_id and new_id != existing:
            event_ids[str(user.pk)] = new_id
            changed = True

    if changed:
        type(appointment).objects.filter(pk=appointment.pk).update(
            google_calendar_event_ids=event_ids
        )


def delete_appointment_events(appointment):
    from apps.accounts.models import User

    event_ids = appointment.google_calendar_event_ids or {}
    if not event_ids:
        return

    users = {str(u.pk): u for u in User.objects.filter(pk__in=event_ids.keys())}
    for user_pk, event_id in event_ids.items():
        user = users.get(user_pk)
        if user:
            try:
                delete_event_for_user(user, event_id)
            except Exception:
                logger.exception("Failed to delete event %s for user %s", event_id, user_pk)
