#Enrutador principal que define qué URL llama a qué app o vista.

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/powerbi/", include("powerbi.urls")),
    path("", TemplateView.as_view(template_name="index.html")),
]
