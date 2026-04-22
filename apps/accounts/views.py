from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.baby.models import WeeklyLog
from apps.files.models import PregnancyFile

from .forms import ProfileForm
from .models import Profile, User


@login_required
def dashboard(request):
    profile = Profile.get_singleton()

    upcoming_appointments = Appointment.objects.filter(
        date__gte=timezone.now()
    ).order_by("date")[:3]

    last_log = WeeklyLog.objects.order_by("-date").first()
    recent_files = PregnancyFile.objects.order_by("-uploaded_at")[:4]

    context = {
        "profile": profile,
        "upcoming_appointments": upcoming_appointments,
        "last_log": last_log,
        "recent_files": recent_files,
    }
    return render(request, "dashboard.html", context)


@login_required
def profile_view(request):
    profile = Profile.get_singleton()

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)

    partner = User.objects.exclude(pk=request.user.pk).first()
    context = {"form": form, "profile": profile, "partner": partner}
    return render(request, "accounts/profile.html", context)


def dev_login(request):
    if not settings.DEBUG:
        return redirect("account_login")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect("/")
        messages.error(request, "Correo o contraseña incorrectos.")
    return redirect("account_login")


def forbidden(request):
    return render(request, "forbidden.html", status=403)
