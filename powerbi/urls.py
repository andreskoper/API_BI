from django.urls import path
from .views import (
    ProcesoPowerBIView,
    RefreshPowerBIStatusView,
    DatasetsView,
    ConfigView
)

urlpatterns = [
    path("parameters/", ProcesoPowerBIView.as_view()),
    path("refresh/status/", RefreshPowerBIStatusView.as_view()),
    path("datasets/", DatasetsView.as_view()),
    path("config/", ConfigView.as_view()),  
]