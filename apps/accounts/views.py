from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.baby.models import WeeklyLog
from apps.files.models import PregnancyFile

from .forms import ProfileForm
from .models import Profile


@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

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
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)

    context = {"form": form, "profile": profile}
    return render(request, "accounts/profile.html", context)


def forbidden(request):
    return render(request, "forbidden.html", status=403)
