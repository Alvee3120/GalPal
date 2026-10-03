"""Public contact form and checkout capture (Module 14), mounted at /api/v1/."""
from django.urls import path

from .views import CheckoutLeadView, ContactMessageView

app_name = "care"

urlpatterns = [
    path("contact/", ContactMessageView.as_view(), name="contact"),
    path("checkout/lead/", CheckoutLeadView.as_view(), name="checkout-lead"),
]
