from dataclasses import dataclass, field

from django.db import transaction

from .models import KickSession

COMPARED_FIELDS = ("count", "target", "goal_reached", "time_to_goal_seconds", "duration_seconds", "notes")


@dataclass
class UpsertResult:
    created: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)  # (existing, incoming) pairs


def upsert_sessions(rows, *, source, logged_by=None):
    """Insert sessions keyed on started_at; existing sessions are never overwritten."""
    result = UpsertResult()
    with transaction.atomic():
        existing = KickSession.objects.in_bulk([row["started_at"] for row in rows], field_name="started_at")
        for row in rows:
            incoming = KickSession(
                started_at=row["started_at"],
                count=row["count"],
                duration_seconds=row.get("duration_seconds"),
                notes=row.get("notes", ""),
                source=source,
                logged_by=logged_by,
            )
            incoming.set_goal_from_duration()

            current = existing.get(incoming.started_at)
            if current is None:
                incoming.save()
                existing[incoming.started_at] = incoming
                result.created.append(incoming)
            elif all(getattr(current, f) == getattr(incoming, f) for f in COMPARED_FIELDS):
                result.unchanged.append(current)
            else:
                result.conflicts.append((current, incoming))
    return result
