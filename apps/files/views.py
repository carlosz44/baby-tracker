from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import PregnancyFileForm
from .models import PregnancyFile


@login_required
def file_list(request):
    files_by_category = {}
    for category_value, category_label in PregnancyFile.CATEGORIES:
        files = PregnancyFile.objects.filter(category=category_value)
        if files.exists():
            files_by_category[category_label] = files

    return render(request, "files/list.html", {"files_by_category": files_by_category})


@login_required
def file_upload(request):
    if request.method == "POST":
        form = PregnancyFileForm(request.POST, request.FILES)
        if form.is_valid():
            pregnancy_file = form.save(commit=False)
            pregnancy_file.uploaded_by = request.user
            pregnancy_file.save()
            messages.success(request, "Archivo subido correctamente.")
            return redirect("file_list")
    else:
        form = PregnancyFileForm()
    return render(request, "files/upload.html", {"form": form})
