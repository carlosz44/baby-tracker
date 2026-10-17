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


OFFSETS_TO_GOAL = [5.2, 30.0, 61.5, 90.0, 120.4, 150.0, 200.0, 250.0, 300.0, 333.4]


def post_counter_session(client, **overrides):
    payload = {
        "started_at": "2026-10-01T20:00:42.500Z",
        "duration_seconds": 340,
        "kick_offsets": OFFSETS_TO_GOAL,
        "notes": "",
        **overrides,
    }
    return client.post("/baby/kick-counter/sessions/", json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_counter_save_creates_session(client, user):
    response = post_counter_session(client)

    assert response.status_code == 200
    session = KickSession.objects.get()
    assert session.source == "counter"
    assert session.count == 10
    assert session.goal_reached
    assert session.time_to_goal_seconds == 333
    assert session.duration_seconds == 340
    assert session.kick_offsets == OFFSETS_TO_GOAL
    assert session.date == date(2026, 10, 1)
    assert session.logged_by == user


@pytest.mark.django_db
def test_counter_save_past_target_uses_tenth_kick(client):
    post_counter_session(client, kick_offsets=OFFSETS_TO_GOAL + [400.0, 420.0], duration_seconds=430)

    session = KickSession.objects.get()
    assert session.count == 12
    assert session.time_to_goal_seconds == 333
    assert session.duration_seconds == 430


@pytest.mark.django_db
def test_counter_save_below_target(client):
    post_counter_session(client, kick_offsets=OFFSETS_TO_GOAL[:4], duration_seconds=7200)

    session = KickSession.objects.get()
    assert session.count == 4
    assert not session.goal_reached
    assert session.time_to_goal_seconds is None


@pytest.mark.django_db
def test_counter_save_is_idempotent(client):
    assert post_counter_session(client).status_code == 200
    assert post_counter_session(client).status_code == 200
    assert KickSession.objects.count() == 1


@pytest.mark.django_db
def test_counter_save_conflict(client):
    post_counter_session(client)
    response = post_counter_session(client, notes="otra")

    assert response.status_code == 409
    assert KickSession.objects.get().notes == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"kick_offsets": [10.0, 5.0]},
        {"kick_offsets": [-1.0]},
        {"kick_offsets": ["5"]},
        {"kick_offsets": OFFSETS_TO_GOAL, "duration_seconds": 100},
        {"started_at": "2999-01-01T00:00:00Z"},
        {"duration_seconds": None},
    ],
)
def test_counter_save_rejects_invalid_payload(client, overrides):
    response = post_counter_session(client, **overrides)

    assert response.status_code == 400
    assert response.json()["error"]
    assert not KickSession.objects.exists()


@pytest.mark.django_db
def test_counter_save_rejects_non_object_body(client):
    response = client.post("/baby/kick-counter/sessions/", "[]", content_type="application/json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_counter_save_requires_post(client):
    assert client.get("/baby/kick-counter/sessions/").status_code == 405


@pytest.mark.django_db
def test_edit_notes_keeps_counter_data(client):
    post_counter_session(client)
    session = KickSession.objects.get()
    assert client.get(f"/baby/kick-counter/{session.pk}/edit/").status_code == 200

    response = client.post(
        f"/baby/kick-counter/{session.pk}/edit/",
        {"started_at": "2026-10-01T15:00", "count": 10, "duration_minutes": 6, "notes": "Después de cenar"},
    )

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.notes == "Después de cenar"
    assert session.started_at == datetime(2026, 10, 1, 20, 0, 42, 500000, tzinfo=UTC)
    assert session.duration_seconds == 340
    assert session.kick_offsets == OFFSETS_TO_GOAL
    assert session.time_to_goal_seconds == 333


@pytest.mark.django_db
def test_edit_count_clears_kick_offsets(client):
    post_counter_session(client)
    session = KickSession.objects.get()

    client.post(
        f"/baby/kick-counter/{session.pk}/edit/",
        {"started_at": "2026-10-01T15:00", "count": 8, "duration_minutes": 6, "notes": ""},
    )

    session.refresh_from_db()
    assert session.kick_offsets == []
    assert session.count == 8
    assert not session.goal_reached


@pytest.mark.django_db
def test_delete_session(client):
    post_counter_session(client)
    session = KickSession.objects.get()

    response = client.post(f"/baby/kick-counter/{session.pk}/delete/")

    assert response.status_code == 302
    assert not KickSession.objects.exists()
