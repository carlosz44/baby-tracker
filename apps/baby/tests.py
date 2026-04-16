from datetime import date

import pytest

from apps.baby.models import KickCount, WeeklyLog


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
def test_kick_count_creation(user):
    kick = KickCount.objects.create(
        date=date.today(),
        count=10,
        duration_minutes=30,
        logged_by=user,
    )
    assert "10 kicks" in str(kick)


@pytest.mark.django_db
def test_weekly_log_list_view(client):
    response = client.get("/baby/logs/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_kick_counter_view(client):
    response = client.get("/baby/kick-counter/")
    assert response.status_code == 200
