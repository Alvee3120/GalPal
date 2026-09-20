"""Public endpoint, mounted at /api/v1/."""
from django.urls import path

from .views import PublicVideoCardListView

app_name = "videos"

urlpatterns = [path("videos/", PublicVideoCardListView.as_view(), name="video-list")]
