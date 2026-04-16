import pytest

from apps.accounts.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def client(user, client):
    client.force_login(user)
    return client
