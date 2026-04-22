from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.files.models import PregnancyFile


@pytest.fixture
def local_file_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_URL = "/media/"
    settings.STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


def create_pregnancy_file(user, **overrides):
    defaults = {
        "file": SimpleUploadedFile(
            "ultrasound.jpg",
            b"fake-image-bytes",
            content_type="image/jpeg",
        ),
        "category": "ultrasound",
        "title": "Ecografia semana 20",
        "notes": "Todo se ve bien.",
        "uploaded_by": user,
    }
    defaults.update(overrides)
    return PregnancyFile.objects.create(**defaults)


@pytest.mark.django_db
def test_file_list_view(client):
    response = client.get("/files/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_file_list_includes_preview_endpoint(client, user, local_file_storage):
    pregnancy_file = create_pregnancy_file(user)

    response = client.get("/files/")

    assert response.status_code == 200
    assert f"/files/{pregnancy_file.pk}/preview/" in response.content.decode()


@pytest.mark.django_db
def test_file_preview_shows_image_and_related_metadata(
    client, user, local_file_storage
):
    appointment = Appointment.objects.create(
        title="Ecografia morfologica",
        appointment_type="ultrasound",
        date=timezone.now() + timedelta(days=2),
    )
    pregnancy_file = create_pregnancy_file(
        user,
        notes="Llevar resultados previos.",
        appointment=appointment,
    )

    response = client.get(f"/files/{pregnancy_file.pk}/preview/")

    content = response.content.decode()
    assert response.status_code == 200
    assert pregnancy_file.title in content
    assert "Llevar resultados previos." in content
    assert appointment.title in content
    assert '<img src="/media/' in content


@pytest.mark.django_db
def test_file_preview_shows_pdf_embed_and_fallback_actions(
    client, user, local_file_storage
):
    pregnancy_file = create_pregnancy_file(
        user,
        file=SimpleUploadedFile(
            "lab-results.pdf",
            b"%PDF-1.4 fake pdf",
            content_type="application/pdf",
        ),
        category="lab_result",
        title="Resultados de laboratorio",
        notes="",
    )

    response = client.get(f"/files/{pregnancy_file.pk}/preview/")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'type="application/pdf"' in content
    assert "Abrir PDF" in content
    assert "No hay una cita asociada." in content


@pytest.mark.django_db
def test_file_upload_view(client):
    response = client.get("/files/upload/")
    assert response.status_code == 200
