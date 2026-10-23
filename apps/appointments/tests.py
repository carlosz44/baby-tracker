from datetime import timedelta

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


def _appointment(days_ago, doctor="", clinic=""):
    return Appointment.objects.create(
        title="Control",
        appointment_type="obstetric",
        date=timezone.now() - timedelta(days=days_ago),
        doctor=doctor,
        clinic=clinic,
    )


@pytest.mark.django_db
def test_new_appointment_prefills_latest_doctor_and_clinic(client):
    _appointment(30, doctor="Dr. Old", clinic="Clínica Old")
    _appointment(10, doctor="Dr. Latest", clinic="Clínica Latest")
    _appointment(5, clinic="Laboratorio")

    form = client.get("/appointments/new/").context["form"]

    assert form["doctor"].value() == "Dr. Latest"
    assert form["clinic"].value() == "Laboratorio"


@pytest.mark.django_db
def test_new_appointment_without_history_has_no_suggestions(client):
    response = client.get("/appointments/new/")

    form = response.context["form"]
    assert form["doctor"].value() is None
    assert "list" not in form.fields["doctor"].widget.attrs
    assert b"<datalist" not in response.content


@pytest.mark.django_db
def test_appointment_form_suggests_past_values_most_used_first(client):
    _appointment(30, doctor="Dr. Rare")
    _appointment(20, doctor="Dr. Usual")
    _appointment(10, doctor="Dr. Usual")

    response = client.get("/appointments/new/")

    assert response.context["form"].fields["doctor"].suggestions == ["Dr. Usual", "Dr. Rare"]
    html = response.content.decode()
    assert 'list="doctor-options"' in html
    assert '<datalist id="doctor-options">' in html


@pytest.mark.django_db
def test_edit_appointment_keeps_its_own_doctor_and_clinic(client):
    own = _appointment(30, doctor="Dr. Own", clinic="Clínica Own")
    _appointment(10, doctor="Dr. Latest", clinic="Clínica Latest")

    form = client.get(f"/appointments/{own.pk}/edit/").context["form"]

    assert form["doctor"].value() == "Dr. Own"
    assert form["clinic"].value() == "Clínica Own"


@pytest.mark.django_db
def test_create_appointment_saves_typed_doctor_over_default(client):
    _appointment(10, doctor="Dr. Latest", clinic="Clínica Latest")

    client.post(
        "/appointments/new/",
        {
            "title": "Ecografía",
            "appointment_type": "ultrasound",
            "date": "2026-11-05T10:00",
            "doctor": "Dr. Other",
            "clinic": "Clínica Latest",
            "notes": "",
        },
    )

    assert Appointment.objects.filter(title="Ecografía", doctor="Dr. Other").exists()
