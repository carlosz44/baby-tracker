from datetime import date, timedelta

import pytest

from apps.accounts.models import Profile


@pytest.mark.django_db
def test_profile_pregnancy_week(user):
    profile = Profile.objects.create(
        user=user,
        due_date=date.today() - timedelta(weeks=12),
    )
    assert profile.pregnancy_week == 12


@pytest.mark.django_db
def test_profile_days_remaining(user):
    profile = Profile.objects.create(
        user=user,
        due_date=date.today(),
    )
    assert profile.days_remaining == 280


@pytest.mark.django_db
def test_dashboard_view(client):
    response = client.get("/")
    assert response.status_code == 200
