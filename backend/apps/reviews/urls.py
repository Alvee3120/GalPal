"""Public endpoints, mounted at /api/v1/."""
from django.urls import path

from .views import RatingBreakdownView, ReviewListCreateView

app_name = "reviews"

urlpatterns = [
    path("reviews/", ReviewListCreateView.as_view(), name="review-list-create"),
    path("reviews/breakdown/", RatingBreakdownView.as_view(), name="review-breakdown"),
]
