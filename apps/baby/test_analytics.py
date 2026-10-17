from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.accounts.models import Profile
from apps.baby.analytics import build_report, latest_alert, session_stats, weekly_summary
from apps.baby.models import KickSession

LIMA = ZoneInfo("America/Lima")
NOW = datetime(2026, 10, 16, 20, 0, tzinfo=LIMA)


def session(day, hour, minutes, *, count=10, duration=None, notes=""):
    seconds = None if minutes is None else minutes * 60
    s = KickSession(
        started_at=datetime(2026, 10, day, hour, 0, tzinfo=LIMA),
        count=count,
        duration_seconds=duration if duration is not None else seconds,
        notes=notes,
    )
    s.set_goal()
    return s


def test_baseline_needs_three_prior_sessions():
    stats = session_stats([session(1, 15, 6), session(2, 15, 6), session(3, 15, 6), session(4, 15, 6)])
    assert [s.baseline for s in stats] == [None, None, None, 6]


def test_slow_session_flagged_above_twice_baseline():
    base = [session(1, 15, 5), session(2, 15, 5), session(3, 15, 5)]
    stats = session_stats(base + [session(4, 15, 10), session(4, 22, 11)])
    assert not stats[3].flagged
    assert stats[4].flagged


def test_baseline_only_uses_previous_seven_days():
    stats = session_stats([session(1, 15, 30), session(2, 15, 30), session(3, 15, 30), session(10, 15, 5)])
    assert stats[3].baseline is None


def test_stalled_session_flagged():
    stats = session_stats([session(5, 15, None, count=4, duration=2 * 60 * 60)])
    assert stats[0].flagged
    assert stats[0].minutes is None


def test_latest_alert_ignores_old_flags():
    old = session_stats([session(1, 15, 5), session(2, 15, 5), session(3, 15, 5), session(4, 15, 20)])
    assert old[3].flagged
    assert latest_alert(old, NOW) is None

    recent = session_stats([session(13, 15, 5), session(14, 15, 5), session(15, 15, 5), session(16, 10, 20)])
    assert latest_alert(recent, NOW).start.day == 16


def test_weekly_summary_compares_with_previous_week():
    stats = session_stats([session(3, 15, 10), session(5, 15, 8), session(12, 15, 6), session(16, 15, 4)])
    summary = weekly_summary(stats, date(2026, 10, 16))
    assert summary == {"sessions": 2, "days": 2, "median": 5, "delta": -4}


def test_build_report_buckets_calendar_and_points():
    sessions = [session(12, 3, 10), session(12, 10, 8), session(14, 23, 4), session(16, 15, 6)]
    report = build_report(sessions, now=NOW, lmp=date(2026, 3, 1), days=30)

    buckets = {b["label"]: b for b in report["chart"]["buckets"]}
    assert buckets["Madrugada"]["median"] == 10
    assert buckets["Noche"]["count"] == 1
    assert buckets["Tarde"]["median"] == 6

    # Mon Oct 12 → Sun Oct 18: one week row, Monday first.
    assert len(report["weeks"]) == 1
    cells = report["weeks"][0]
    assert cells[0]["date"] == date(2026, 10, 12)
    assert cells[0]["level"] == 2
    assert cells[1]["count"] == 0 and cells[1]["in_range"]
    assert cells[4]["is_today"]
    assert not cells[5]["in_range"]

    points = report["chart"]["points"]
    assert len(points) == 4
    assert points[0]["week"] == 32
    assert report["rows"][0].start.day == 16


def test_build_report_range_trims_old_sessions():
    sessions = [session(1, 15, 6), session(16, 15, 6)]
    report = build_report(sessions, now=NOW, days=14)
    assert report["start_day"] == date(2026, 10, 3)
    assert len(report["chart"]["points"]) == 1


def test_build_report_without_sessions():
    report = build_report([], now=NOW)
    assert not report["has_data"]
    assert report["summary"]["sessions"] == 0


@pytest.mark.django_db
def test_kick_stats_view(client):
    Profile.objects.create(due_date=date(2026, 3, 1))
    for days_ago in range(4):
        KickSession.objects.create(started_at=timezone.now() - timedelta(days=days_ago), count=10, time_to_goal_seconds=300, goal_reached=True)

    response = client.get("/baby/kick-counter/stats/?range=all")

    assert response.status_code == 200
    html = response.content.decode()
    assert "Constancia" in html
    assert 'id="kick-stats-data"' in html


@pytest.mark.django_db
def test_kick_stats_view_empty_and_bad_range(client):
    response = client.get("/baby/kick-counter/stats/?range=bogus")
    assert response.status_code == 200
    assert response.context["range_key"] == "30"
    assert "Todavía no hay sesiones" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_shows_kick_tile_and_alert(client):
    now = timezone.now()
    for days_ago in (4, 3, 2):
        KickSession.objects.create(started_at=now - timedelta(days=days_ago), count=10, time_to_goal_seconds=300, goal_reached=True)
    KickSession.objects.create(started_at=now - timedelta(hours=1), count=10, time_to_goal_seconds=900, goal_reached=True)

    response = client.get("/")

    html = response.content.decode()
    assert response.status_code == 200
    assert "Ver análisis" in html
    assert "más del doble de lo habitual" in html
