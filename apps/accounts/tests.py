from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Profile


@pytest.mark.django_db
def test_profile_pregnancy_week():
    profile = Profile.objects.create(
        due_date=timezone.localdate() - timedelta(weeks=12),
    )
    assert profile.pregnancy_week == 12


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
        ("/baby/logs/", "logs"),
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
    assert "/notifications/" not in nav
    assert 'aria-current="page"' in nav


@pytest.mark.django_db
def test_profile_has_theme_switch_and_logout(client):
    html = client.get("/accounts/profile/").content.decode()
    assert 'data-theme-set="dark"' in html
    assert "/accounts/logout/" in html
