"""Public endpoints, mounted at /api/v1/."""
from django.urls import path

from .views import CalculateShippingView, DistrictListView, MethodListView, ZoneListView

app_name = "shipping"

urlpatterns = [
    path("shipping/zones/", ZoneListView.as_view(), name="zone-list"),
    path("shipping/methods/", MethodListView.as_view(), name="method-list"),
    path("shipping/districts/", DistrictListView.as_view(), name="district-list"),
    path("shipping/calculate/", CalculateShippingView.as_view(), name="calculate"),
]
