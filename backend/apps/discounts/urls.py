"""Public discount endpoints, mounted at /api/v1/."""
from django.urls import path

from .views import ActiveDiscountListView

app_name = "discounts"

urlpatterns = [path("discounts/active/", ActiveDiscountListView.as_view(), name="active")]
