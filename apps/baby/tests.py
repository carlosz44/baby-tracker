import io
import json
from datetime import UTC, date, datetime

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.baby.models import KickSession, WeeklyLog
from apps.baby.services import upsert_sessions

LIMA_EVENING = datetime(2026, 10, 1, 4, 30, tzinfo=UTC)  # 23:30 on Sep 30 in Lima


@pytest.mark.django_db
def test_weekly_log_creation(user):
    log = WeeklyLog.objects.create(
        week_number=20,
        weight_kg=65.5,
        mood="good",
        logged_by=user,
    )
    assert str(log).startswith("Week 20")


@pytest.mark.django_db
def test_kick_session_creation(user):
    session = KickSession.objects.create(
        started_at=timezone.now(),
        count=10,
        duration_seconds=450,
        logged_by=user,
    )
    assert "10 kicks" in str(session)
    assert session.duration_minutes == 8


@pytest.mark.django_db
def test_kick_session_date_is_lima_day():
    session = KickSession.objects.create(started_at=LIMA_EVENING, count=10)
    assert session.date == date(2026, 9, 30)


@pytest.mark.django_db
def test_weekly_log_list_view(client):
    response = client.get("/baby/logs/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_kick_counter_view(client):
    KickSession.objects.create(started_at=timezone.now(), count=10, notes="Después de cenar")
    response = client.get("/baby/kick-counter/")
    assert response.status_code == 200
    assert "Después de cenar" in response.content.decode()


@pytest.mark.django_db
def test_kick_counter_post_sets_goal_fields(client, user):
    response = client.post(
        "/baby/kick-counter/",
        {"started_at": "2026-10-16T15:30", "count": 10, "duration_minutes": 7, "notes": ""},
    )
    assert response.status_code == 302
    session = KickSession.objects.get()
    assert timezone.localtime(session.started_at).hour == 15
    assert session.date == date(2026, 10, 16)
    assert session.goal_reached
    assert session.duration_seconds == 420
    assert session.time_to_goal_seconds == 420
    assert session.source == "manual"
    assert session.logged_by == user


@pytest.mark.django_db
def test_kick_counter_post_past_target_has_no_time_to_goal(client):
    client.post("/baby/kick-counter/", {"started_at": "2026-10-16T15:30", "count": 14, "duration_minutes": 12})
    session = KickSession.objects.get()
    assert session.goal_reached
    assert session.time_to_goal_seconds is None


@pytest.mark.django_db
def test_kick_counter_post_rejects_duplicate_start(client):
    data = {"started_at": "2026-10-16T15:30", "count": 10, "duration_minutes": 7}
    client.post("/baby/kick-counter/", data)
    response = client.post("/baby/kick-counter/", data)
    assert response.status_code == 200
    assert "Ya existe una sesión" in response.content.decode()
    assert KickSession.objects.count() == 1


@pytest.mark.django_db
def test_upsert_sessions_is_idempotent():
    rows = [
        {"started_at": LIMA_EVENING, "count": 10, "duration_seconds": 360},
        {"started_at": LIMA_EVENING, "count": 10, "duration_seconds": 360},
    ]
    first = upsert_sessions(rows, source="screenshot")
    second = upsert_sessions(rows, source="screenshot")

    assert len(first.created) == 1
    assert len(first.unchanged) == 1
    assert len(second.unchanged) == 2
    session = KickSession.objects.get()
    assert session.goal_reached
    assert session.time_to_goal_seconds == 360
    assert session.logged_by is None


@pytest.mark.django_db
def test_upsert_sessions_reports_conflict_without_overwriting():
    upsert_sessions([{"started_at": LIMA_EVENING, "count": 10, "duration_seconds": 360}], source="screenshot")
    result = upsert_sessions([{"started_at": LIMA_EVENING, "count": 10, "duration_seconds": 420}], source="screenshot")

    assert len(result.conflicts) == 1
    assert KickSession.objects.get().duration_seconds == 360


@pytest.mark.django_db
def test_load_kick_sessions_from_stdin(monkeypatch):
    rows = [
        {"started_at": "2026-09-30T23:30:00-05:00", "count": 10, "minutes": 6, "notes": ""},
        {"started_at": "2026-10-10T17:00", "count": 10, "minutes": 11, "notes": "Después de cenar"},
    ]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(rows)))
    out = io.StringIO()
    call_command("load_kick_sessions", source="screenshot", stdout=out)

    assert "created 2" in out.getvalue()
    assert KickSession.objects.get(started_at=LIMA_EVENING).date == date(2026, 9, 30)
    noted = KickSession.objects.get(notes="Después de cenar")
    assert timezone.localtime(noted.started_at).hour == 17
    assert noted.source == "screenshot"


@pytest.mark.django_db
def test_load_kick_sessions_dry_run_writes_nothing(tmp_path):
    path = tmp_path / "sessions.json"
    path.write_text(json.dumps([{"started_at": "2026-09-30T23:30:00-05:00", "count": 10, "minutes": 6}]))
    out = io.StringIO()
    call_command("load_kick_sessions", str(path), source="screenshot", dry_run=True, stdout=out)

    assert "[dry run] created 1" in out.getvalue()
    assert not KickSession.objects.exists()
