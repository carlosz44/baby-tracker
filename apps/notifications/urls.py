from django.urls import path

from . import views

urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("diagnostics/", views.notification_diagnostics, name="notification_diagnostics"),
    path("<int:pk>/retry/", views.notification_retry, name="notification_retry"),
    path("<int:pk>/dismiss/", views.notification_dismiss, name="notification_dismiss"),
]
