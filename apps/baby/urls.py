from django.urls import path

from . import views

urlpatterns = [
    path("logs/", views.weekly_log_list, name="weekly_log_list"),
    path("logs/new/", views.weekly_log_create, name="weekly_log_create"),
    path("kick-counter/", views.kick_counter, name="kick_counter"),
    path("birth-plan/", views.birth_plan, name="birth_plan"),
]
