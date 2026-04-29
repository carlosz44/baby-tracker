import logging
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from allauth.socialaccount.models import SocialApp, SocialToken

logger = logging.getLogger(__name__)

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


class MissingCalendarAuth(Exception):
    """User has no Google token, or no refresh token to keep the session alive."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


# User-facing messages for each reason a Google session can't be used.
# Both the sync notification and the diagnostics page render from these.
AUTH_REASON_MESSAGES = {
    "no_token": "Esta cuenta aún no ha conectado Google Calendar.",
    "no_refresh_token": (
        "Falta el refresh token de Google. Cierra sesión y vuelve a "
        "iniciar sesión con esta cuenta para autorizar el calendario."
    ),
    "invalid_scope": (
        "La cuenta autorizó la app pero sin el permiso de Google Calendar. "
        "Cierra sesión y vuelve a iniciar sesión, asegurándote de aprobar "
        "el permiso de calendario."
    ),
    "refresh_failed": (
        "Google rechazó el refresh token. Cierra sesión y vuelve a iniciar "
        "sesión con esta cuenta."
    ),
}


def auth_required_message(reason: str) -> str:
    return AUTH_REASON_MESSAGES.get(
        reason, "No se pudo autenticar con Google. Cierra sesión y vuelve a iniciar sesión."
    )


def _classify_refresh_error(exc: RefreshError) -> str:
    """Map a google-auth RefreshError to a MissingCalendarAuth reason."""
    text = str(exc).lower()
    if "invalid_scope" in text:
        return "invalid_scope"
    return "refresh_failed"


def _get_oauth_app():
    app = SocialApp.objects.filter(provider="google").first()
    if app:
        return app.client_id, app.secret
    google_cfg = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
    return google_cfg.get("client_id", ""), google_cfg.get("secret", "")


def _build_credentials(token: SocialToken) -> Credentials:
    client_id, client_secret = _get_oauth_app()
    expiry = None
    if token.expires_at:
        expiry = token.expires_at.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return Credentials(
        token=token.token,
        refresh_token=token.token_secret,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[CALENDAR_SCOPE],
        expiry=expiry,
    )


def _persist_refreshed_credentials(token: SocialToken, credentials: Credentials) -> None:
    if not credentials.token or credentials.token == token.token:
        return
    token.token = credentials.token
    if credentials.expiry:
        token.expires_at = credentials.expiry.replace(tzinfo=dt_timezone.utc)
    token.save(update_fields=["token", "expires_at"])


def _get_token_for_user(user) -> SocialToken:
    token = SocialToken.objects.filter(
        account__user=user,
        account__provider="google",
    ).first()
    if not token:
        raise MissingCalendarAuth("no_token")
    if not token.token_secret:
        raise MissingCalendarAuth("no_refresh_token")
    return token


def get_calendar_service(user):
    """Return (service, token, credentials) for the given user.

    Raises MissingCalendarAuth if the user has no usable token. Caller is
    responsible for invoking _persist_refreshed_credentials after API use
    (done inside the upsert/delete helpers below).
    """
    token = _get_token_for_user(user)
    credentials = _build_credentials(token)
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    return service, token, credentials


def resync_future_appointments() -> dict:
    """Re-run sync_appointment for every appointment whose date is now-or-future.

    Returns a summary dict: {appointments: N, missing_event_for_user: M, errors: K}.
    Intended for the "Resincronizar todas las citas" UI action — covers users
    that were missing events for older appointments after re-authenticating.
    """
    from django.utils import timezone

    from .models import Appointment

    now = timezone.now()
    appointments = list(Appointment.objects.filter(date__gte=now))
    summary = {
        "appointments": len(appointments),
        "errors": 0,
    }
    for appointment in appointments:
        try:
            sync_appointment(appointment)
        except Exception:
            logger.exception("Resync failed for appointment %s", appointment.pk)
            summary["errors"] += 1
    return summary


def run_calendar_diagnostics() -> list[dict]:
    """Per-user calendar auth + API ping report.

    Returns a list of dicts (one per user). Each dict has at least:
      email, auth_status ("ok" | "missing"),
    and when auth_status == "ok":
      access_token_present, refresh_token_present, expires_at,
      api_ping ("ok" | "failed"), and either calendar_count or error.
    When auth_status == "missing": auth_reason ("no_token" | "no_refresh_token").

    Persists any access token refreshed during the live API call.
    """
    from apps.accounts.models import User

    results: list[dict] = []
    for user in User.objects.order_by("email"):
        result: dict = {"email": user.email}

        try:
            service, token, credentials = get_calendar_service(user)
        except MissingCalendarAuth as exc:
            result["auth_status"] = "missing"
            result["auth_reason"] = exc.reason
            results.append(result)
            continue

        result["auth_status"] = "ok"
        result["access_token_present"] = bool(token.token)
        result["refresh_token_present"] = bool(token.token_secret)
        result["expires_at"] = token.expires_at

        original_token = token.token
        try:
            resp = service.calendarList().list(maxResults=1).execute()
            result["api_ping"] = "ok"
            result["calendar_count"] = len(resp.get("items", []))
            if credentials.token and credentials.token != original_token:
                _persist_refreshed_credentials(token, credentials)
                result["refreshed"] = True
        except RefreshError as e:
            reason = _classify_refresh_error(e)
            result["auth_status"] = "missing"
            result["auth_reason"] = reason
            result["error"] = auth_required_message(reason)
            result["raw_error"] = f"{type(e).__name__}: {e}"
        except HttpError as e:
            result["api_ping"] = "failed"
            result["error"] = f"{e.resp.status} {e.reason}"
        except Exception as e:
            result["api_ping"] = "failed"
            result["error"] = f"{type(e).__name__}: {e}"

        results.append(result)

    return results


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
    """Create or update the appointment on user's primary calendar. Returns event id.

    Raises MissingCalendarAuth if the user can't be authenticated.
    """
    service, token, credentials = get_calendar_service(user)
    body = _build_event_body(appointment)

    try:
        if event_id:
            try:
                event = service.events().update(
                    calendarId="primary", eventId=event_id, body=body
                ).execute()
            except HttpError as e:
                if e.resp.status in (404, 410):
                    event = service.events().insert(
                        calendarId="primary", body=body
                    ).execute()
                else:
                    raise
        else:
            event = service.events().insert(calendarId="primary", body=body).execute()
        return event.get("id")
    except RefreshError as e:
        raise MissingCalendarAuth(_classify_refresh_error(e)) from e
    finally:
        _persist_refreshed_credentials(token, credentials)


def delete_event_for_user(user, event_id):
    """Delete the user's calendar event. Raises MissingCalendarAuth if not authed."""
    service, token, credentials = get_calendar_service(user)
    try:
        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
        except HttpError as e:
            if e.resp.status in (404, 410):
                logger.info("Event %s already gone for user %s", event_id, user.email)
            else:
                raise
    except RefreshError as e:
        raise MissingCalendarAuth(_classify_refresh_error(e)) from e
    finally:
        _persist_refreshed_credentials(token, credentials)


def sync_appointment(appointment):
    """Create or update event on every user's calendar that has Google linked."""
    from apps.accounts.models import User
    from apps.notifications.models import Notification
    from apps.notifications.services import mark_resolved, record_notification

    from .notification_kinds import (
        ACTION_UPSERT,
        CALENDAR_AUTH_REQUIRED,
        CALENDAR_SYNC_FAILED,
        sync_dedupe_key,
    )

    event_ids = dict(appointment.google_calendar_event_ids or {})
    changed = False

    for user in User.objects.all():
        existing = event_ids.get(str(user.pk))
        dedupe_key = sync_dedupe_key(appointment.pk, user.pk, ACTION_UPSERT)
        try:
            new_id = upsert_event_for_user(appointment, user, event_id=existing)
        except MissingCalendarAuth as exc:
            record_notification(
                kind=CALENDAR_AUTH_REQUIRED,
                title=f"Reconectar Google Calendar para {user.email}",
                message=auth_required_message(exc.reason),
                severity=Notification.SEVERITY_ERROR,
                payload={
                    "appointment_id": appointment.pk,
                    "user_id": user.pk,
                    "action": ACTION_UPSERT,
                    "reason": exc.reason,
                },
                user=user,
                dedupe_key=dedupe_key,
            )
            continue
        except Exception as exc:
            logger.exception("Calendar sync failed for user %s", user.email)
            record_notification(
                kind=CALENDAR_SYNC_FAILED,
                title=f"No se pudo sincronizar la cita con el calendario de {user.email}",
                message=f"{appointment.title} — {exc}",
                severity=Notification.SEVERITY_WARNING,
                payload={
                    "appointment_id": appointment.pk,
                    "user_id": user.pk,
                    "action": ACTION_UPSERT,
                },
                user=user,
                dedupe_key=dedupe_key,
            )
            continue

        mark_resolved(dedupe_key=dedupe_key)
        if new_id and new_id != existing:
            event_ids[str(user.pk)] = new_id
            changed = True

    if changed:
        type(appointment).objects.filter(pk=appointment.pk).update(
            google_calendar_event_ids=event_ids
        )


def delete_appointment_events(appointment):
    from apps.accounts.models import User
    from apps.notifications.models import Notification
    from apps.notifications.services import mark_resolved, record_notification

    from .notification_kinds import (
        ACTION_DELETE,
        CALENDAR_AUTH_REQUIRED,
        CALENDAR_SYNC_FAILED,
        sync_dedupe_key,
    )

    event_ids = appointment.google_calendar_event_ids or {}
    if not event_ids:
        return

    users = {str(u.pk): u for u in User.objects.filter(pk__in=event_ids.keys())}
    for user_pk, event_id in event_ids.items():
        user = users.get(user_pk)
        if not user:
            continue
        dedupe_key = sync_dedupe_key(appointment.pk, user.pk, ACTION_DELETE)
        try:
            delete_event_for_user(user, event_id)
        except MissingCalendarAuth as exc:
            record_notification(
                kind=CALENDAR_AUTH_REQUIRED,
                title=f"Reconectar Google Calendar para {user.email}",
                message=auth_required_message(exc.reason),
                severity=Notification.SEVERITY_ERROR,
                payload={
                    "appointment_id": appointment.pk,
                    "user_id": user.pk,
                    "event_id": event_id,
                    "action": ACTION_DELETE,
                    "reason": exc.reason,
                },
                user=user,
                dedupe_key=dedupe_key,
            )
            continue
        except Exception as exc:
            logger.exception("Failed to delete event %s for user %s", event_id, user_pk)
            record_notification(
                kind=CALENDAR_SYNC_FAILED,
                title=f"No se pudo borrar la cita en el calendario de {user.email}",
                message=str(exc),
                severity=Notification.SEVERITY_WARNING,
                payload={
                    "appointment_id": appointment.pk,
                    "user_id": user.pk,
                    "event_id": event_id,
                    "action": ACTION_DELETE,
                },
                user=user,
                dedupe_key=dedupe_key,
            )
            continue

        mark_resolved(dedupe_key=dedupe_key)
