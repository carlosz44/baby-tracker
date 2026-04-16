from django.urls import path

from . import views

urlpatterns = [
    path("", views.file_list, name="file_list"),
    path("upload/", views.file_upload, name="file_upload"),
]
