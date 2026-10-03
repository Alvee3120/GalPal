"""Customer care admin endpoints (Module 14), mounted at /api/v1/admin/. Admin only, except messages/ and
abandoned-checkouts/, which CCE can use too."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views_admin import (
    AbandonedCheckoutViewSet,
    ContactMessageViewSet,
    CustomerNoteDetailView,
    CustomerNotesView,
    CustomerProfileView,
    CustomerTagsView,
    CustomerTagViewSet,
)

router = SimpleRouter()
router.register("care/tags", CustomerTagViewSet, basename="care-tag")
router.register("care/messages", ContactMessageViewSet, basename="care-message")
router.register("care/abandoned-checkouts", AbandonedCheckoutViewSet, basename="care-abandoned-checkout")

urlpatterns = [
    path("care/customers/<int:pk>/", CustomerProfileView.as_view(), name="care-customer"),
    path("care/customers/<int:pk>/notes/", CustomerNotesView.as_view(), name="care-customer-notes"),
    path("care/customers/<int:pk>/tags/", CustomerTagsView.as_view(), name="care-customer-tags"),
    path("care/notes/<int:pk>/", CustomerNoteDetailView.as_view(), name="care-note"),
    *router.urls,
]
