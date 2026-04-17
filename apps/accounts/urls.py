from django.conf import settings
from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
]

if settings.DEBUG:
    urlpatterns += [
        path("dev-login/", views.dev_login, name="dev_login"),
    ]
