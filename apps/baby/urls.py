from django.urls import path

from . import views

urlpatterns = [
    path("logs/", views.weekly_log_list, name="weekly_log_list"),
    path("logs/new/", views.weekly_log_create, name="weekly_log_create"),
    path("kick-counter/", views.kick_counter, name="kick_counter"),
    path("kick-counter/sessions/", views.kick_session_save, name="kick_session_save"),
    path("kick-counter/<int:pk>/edit/", views.kick_session_edit, name="kick_session_edit"),
    path("kick-counter/<int:pk>/delete/", views.kick_session_delete, name="kick_session_delete"),
    path("birth-plan/", views.birth_plan, name="birth_plan"),
]
