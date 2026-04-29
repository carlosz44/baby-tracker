"""Diagnose Google Calendar sync state for every user.

Prints a per-user report showing whether they have a SocialToken, a refresh
token, expiry, and whether a live calendar API ping succeeds. Useful to confirm
the cause of sync failures before/after the user re-logs in.
"""
from django.core.management.base import BaseCommand

from apps.appointments.calendar_service import run_calendar_diagnostics


class Command(BaseCommand):
    help = "Print Google Calendar sync diagnostics for every user."

    def handle(self, *args, **options):
        results = run_calendar_diagnostics()
        if not results:
            self.stdout.write("No users.")
            return

        for r in results:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{r['email']}"))
            if r["auth_status"] == "missing":
                self.stdout.write(self.style.ERROR(
                    f"  auth: MISSING ({r['auth_reason']})"
                ))
                continue

            self.stdout.write(
                f"  access_token: {'present' if r['access_token_present'] else 'EMPTY'}"
            )
            self.stdout.write(
                f"  refresh_token: {'present' if r['refresh_token_present'] else 'EMPTY'}"
            )
            self.stdout.write(f"  expires_at: {r['expires_at']}")

            if r["api_ping"] == "ok":
                self.stdout.write(self.style.SUCCESS(
                    f"  api ping: ok ({r['calendar_count']} calendars visible)"
                ))
                if r.get("refreshed"):
                    self.stdout.write("  note: access token was refreshed and persisted")
            else:
                self.stdout.write(self.style.ERROR(f"  api ping: FAILED ({r['error']})"))
