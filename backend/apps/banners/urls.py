"""Public endpoint, mounted at /api/v1/."""
from django.urls import path

from .views import HeroSliderView

app_name = "banners"

urlpatterns = [path("hero-banners/", HeroSliderView.as_view(), name="hero-slider")]
