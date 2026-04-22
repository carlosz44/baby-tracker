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
