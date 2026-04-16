from django.utils import timezone

import pytest

from apps.appointments.models import Appointment


@pytest.mark.django_db
def test_appointment_creation():
    appointment = Appointment.objects.create(
        title="Week 20 Ultrasound",
        appointment_type="ultrasound",
        date=timezone.now(),
        doctor="Dr. García",
        clinic="Clínica San Felipe",
    )
    assert str(appointment).startswith("Week 20 Ultrasound")


@pytest.mark.django_db
def test_appointment_list_view(client):
    response = client.get("/appointments/")
    assert response.status_code == 200
