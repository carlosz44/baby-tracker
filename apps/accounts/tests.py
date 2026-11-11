from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Profile

BIRTH_UTC = datetime(2099, 3, 15, 12, 0, tzinfo=UTC)  # 07:00 in Lima


def test_birth_countdown_splits_time_left(monkeypatch):
    left = timedelta(days=2, hours=3, minutes=4, seconds=5)
    monkeypatch.setattr(timezone, "now", lambda: BIRTH_UTC - left)
    assert Profile(scheduled_birth_at=BIRTH_UTC).birth_countdown == {
        "total_seconds": 183845,
        "days": 2,
        "hours": 3,
        "minutes": 4,
        "seconds": 5,
    }


def test_birth_countdown_stays_at_zero_once_passed(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: BIRTH_UTC + timedelta(days=1))
    assert Profile(scheduled_birth_at=BIRTH_UTC).birth_countdown["total_seconds"] == 0


def test_birth_countdown_is_none_without_date():
    assert Profile().birth_countdown is None


@pytest.mark.django_db
def test_dashboard_shows_countdown_in_lima_time(client):
    Profile.objects.create(
        due_date=timezone.localdate(),
        scheduled_birth_at=BIRTH_UTC,
    )
    html = client.get("/").content.decode()
    assert 'data-birth-countdown="2099-03-15T07:00:00-05:00"' in html
    assert "· 07:00" in html
    assert "data-countdown-done hidden" in html
    assert "js/birth_countdown" in html
    # The FUR-based estimate would compete with the real date.
    assert "Días para la Fecha Probable" not in html


@pytest.mark.django_db
def test_dashboard_without_birth_date_keeps_estimate_tile(client):
    Profile.objects.create(due_date=timezone.localdate())
    html = client.get("/").content.decode()
    assert "data-birth-countdown" not in html
    assert "js/birth_countdown" not in html
    assert "Días para la Fecha Probable" in html


@pytest.mark.django_db
def test_dashboard_shows_final_message_once_birth_time_passed(client):
    Profile.objects.create(scheduled_birth_at=timezone.now() - timedelta(minutes=1))
    html = client.get("/").content.decode()
    assert "data-countdown-clock hidden" in html
    assert "data-countdown-done hidden" not in html


@pytest.mark.django_db
def test_profile_saves_birth_datetime_as_lima_time(client):
    due_date = timezone.localdate()
    response = client.post(
        "/accounts/profile/",
        {"due_date": due_date.isoformat(), "scheduled_birth_at": "2099-03-15T07:00"},
    )
    assert response.status_code == 302

    profile = Profile.get_singleton()
    assert profile.scheduled_birth_at == BIRTH_UTC
    assert profile.due_date == due_date
    assert 'value="2099-03-15T07:00"' in client.get("/accounts/profile/").content.decode()


@pytest.mark.django_db
def test_profile_can_clear_birth_datetime(client):
    Profile.objects.create(scheduled_birth_at=BIRTH_UTC)
    response = client.post("/accounts/profile/", {"due_date": "", "scheduled_birth_at": ""})
    assert response.status_code == 302
    assert Profile.get_singleton().scheduled_birth_at is None


@pytest.mark.django_db
def test_profile_pregnancy_week():
    profile = Profile.objects.create(
        due_date=timezone.localdate() - timedelta(weeks=12),
    )
    assert profile.pregnancy_week == 12


def test_gestational_age_counts_weeks_plus_days():
    profile = Profile(due_date=timezone.localdate() - timedelta(weeks=36, days=3))
    assert profile.gestational_age == "36+3"


def test_gestational_age_is_none_without_fur():
    assert Profile().gestational_age is None


@pytest.mark.django_db
def test_dashboard_shows_gestational_age_in_countdown(client):
    Profile.objects.create(
        due_date=timezone.localdate() - timedelta(weeks=36, days=3),
        scheduled_birth_at=BIRTH_UTC,
    )
    html = client.get("/").content.decode()
    assert "Semana 36+3" in html
    assert "Semana Actual" not in html


@pytest.mark.django_db
def test_profile_days_remaining():
    profile = Profile.objects.create(
        due_date=timezone.localdate(),
    )
    assert profile.days_remaining == 280


@pytest.mark.django_db
def test_dashboard_view(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path, section",
    [
        ("/", "home"),
        ("/baby/kick-counter/history/", "kicks"),
        ("/baby/birth-plan/", "birth_plan"),
        ("/notifications/", "notifications"),
        ("/accounts/profile/", "profile"),
    ],
)
def test_nav_section_marks_active_destination(client, path, section):
    response = client.get(path)
    assert response.context["nav_section"] == section


@pytest.mark.django_db
def test_bottom_nav_has_only_destinations(client):
    html = client.get("/").content.decode()
    nav = html[html.index('aria-label="Secciones"'):]
    nav = nav[: nav.index("</nav>")]
    assert nav.count("<a") == 5
    assert 'href="/baby/birth-plan/"' in nav
    assert "/notifications/" not in nav
    assert 'aria-current="page"' in nav


@pytest.mark.django_db
def test_profile_has_theme_switch_and_logout(client):
    html = client.get("/accounts/profile/").content.decode()
    assert 'data-theme-set="dark"' in html
    assert "/accounts/logout/" in html
