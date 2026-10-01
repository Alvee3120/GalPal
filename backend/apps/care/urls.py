"""Public contact form, checkout capture, and customer return requests (Module 14), mounted at /api/v1/."""
from django.urls import path

from .views import CheckoutLeadView, ContactMessageView, MyReturnRequestView

app_name = "care"

urlpatterns = [
    path("contact/", ContactMessageView.as_view(), name="contact"),
    path("checkout/lead/", CheckoutLeadView.as_view(), name="checkout-lead"),
    path("orders/<str:number>/return-request/", MyReturnRequestView.as_view(), name="return-request"),
]
