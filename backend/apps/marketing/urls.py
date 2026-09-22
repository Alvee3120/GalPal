"""Public endpoint, mounted at /api/v1/."""
from django.urls import path

from .views import TrackEventView

app_name = "marketing"

urlpatterns = [path("tracking/events/", TrackEventView.as_view(), name="track-event")]
