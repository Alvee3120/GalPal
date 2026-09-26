"""Admin-panel endpoints, mounted at /api/v1/admin/. Every route here is Admin-only unless
it lives under /admin/orders/ (Module 10), the only area a CCE may reach."""
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()  # SimpleRouter: no public API-root view listing admin URLs
router.register("staff", views.StaffViewSet, basename="admin-staff")
router.register("customers", views.CustomerViewSet, basename="admin-customer")
router.register("users", views.UserViewSet, basename="admin-user")  # User Management: every role

urlpatterns = [path("", include(router.urls))]
