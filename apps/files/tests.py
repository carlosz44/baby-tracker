import pytest


@pytest.mark.django_db
def test_file_list_view(client):
    response = client.get("/files/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_file_upload_view(client):
    response = client.get("/files/upload/")
    assert response.status_code == 200
