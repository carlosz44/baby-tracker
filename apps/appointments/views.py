from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AppointmentForm
from .models import Appointment


@login_required
def appointment_list(request):
    now = timezone.now()
    upcoming = Appointment.objects.filter(date__gte=now).order_by("date")
    past = Appointment.objects.filter(date__lt=now).order_by("-date")
    context = {"upcoming": upcoming, "past": past}
    return render(request, "appointments/list.html", context)


@login_required
def appointment_create(request):
    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cita creada.")
            return redirect("appointment_list")
    else:
        form = AppointmentForm()
    return render(request, "appointments/form.html", {"form": form, "editing": False})


@login_required
def appointment_edit(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
            messages.success(request, "Cita actualizada.")
            return redirect("appointment_list")
    else:
        form = AppointmentForm(instance=appointment)
    return render(request, "appointments/form.html", {"form": form, "editing": True, "appointment": appointment})


@login_required
def appointment_delete(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":
        appointment.delete()
        messages.success(request, "Cita eliminada.")
        return redirect("appointment_list")
    return render(request, "appointments/confirm_delete.html", {"appointment": appointment})
