from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.accounts.views import dashboard, forbidden

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("appointments/", include("apps.appointments.urls")),
    path("files/", include("apps.files.urls")),
    path("baby/", include("apps.baby.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("forbidden/", forbidden, name="forbidden"),
    path("privacy/", TemplateView.as_view(template_name="privacy.html"), name="privacy"),
    path("", dashboard, name="dashboard"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
