"""Public endpoint, mounted at /api/v1/."""
from django.urls import path

from .views import HeroSliderView, MegaMenuBannersView

app_name = "banners"

urlpatterns = [
    path("hero-banners/", HeroSliderView.as_view(), name="hero-slider"),
    path("mega-menu/banners/", MegaMenuBannersView.as_view(), name="mega-menu-banners"),
]
