import logging
from datetime import timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from allauth.socialaccount.models import SocialApp, SocialToken

logger = logging.getLogger(__name__)


def get_calendar_service(user):
    """Build and return a Google Calendar API service for the given user."""
    token = SocialToken.objects.filter(
        account__user=user,
        account__provider="google",
    ).first()

    if not token:
        logger.warning("No Google token found for user %s", user.email)
        return None

    app = SocialApp.objects.get(provider="google")

    credentials = Credentials(
        token=token.token,
        refresh_token=token.token_secret,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=app.client_id,
        client_secret=app.secret,
    )

    return build("calendar", "v3", credentials=credentials)


def create_event(appointment, attendee_users):
    """Create a Google Calendar event. Returns the event ID or None."""
    user = attendee_users[0] if attendee_users else None
    if not user:
        return None

    service = get_calendar_service(user)
    if not service:
        return None

    end_time = appointment.date + timedelta(hours=1)

    event_body = {
        "summary": appointment.title,
        "description": appointment.notes or "",
        "start": {
            "dateTime": appointment.date.isoformat(),
            "timeZone": "America/Lima",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "America/Lima",
        },
        "attendees": [{"email": u.email} for u in attendee_users if u.email],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60},
                {"method": "popup", "minutes": 1440},
            ],
        },
    }

    if appointment.clinic:
        event_body["location"] = appointment.clinic

    event = service.events().insert(calendarId="primary", body=event_body).execute()
    return event.get("id")


def delete_event(user, event_id):
    """Delete a Google Calendar event. Silently ignores 404/410 errors."""
    service = get_calendar_service(user)
    if not service:
        return

    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status in (404, 410):
            logger.info("Calendar event %s already deleted", event_id)
        else:
            raise
