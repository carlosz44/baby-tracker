from django.urls import path

from . import views

urlpatterns = [
    path("", views.file_list, name="file_list"),
    path("upload/", views.file_upload, name="file_upload"),
    path("<int:pk>/preview/", views.file_preview, name="file_preview"),
]
