"""Public endpoint, mounted at /api/v1/: the payment gateway's IPN/webhook callback."""
from django.urls import path

from .views import PaymentCallbackView

app_name = "payments"

urlpatterns = [path("payments/callback/<slug:gateway>/", PaymentCallbackView.as_view(), name="callback")]
