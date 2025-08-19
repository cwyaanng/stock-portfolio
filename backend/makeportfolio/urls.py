from django.urls import path
from .views import run_montecarlo, top3_nasdaq100

urlpatterns = [
    path("montecarlo/", run_montecarlo, name="run_montecarlo"),
    path("nasdaq100/top3/", top3_nasdaq100)
]
