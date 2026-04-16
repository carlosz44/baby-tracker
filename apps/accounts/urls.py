from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    path("dev-login/", views.dev_login, name="dev_login"),
]
