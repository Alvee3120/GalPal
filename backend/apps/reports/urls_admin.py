"""CSV export endpoints (Module 17), mounted at /api/v1/admin/. Admin only (CCE gets 403). Report figures: /admin/dashboard/."""
from django.urls import path

from .views_admin import CustomerExportView, OrderExportView, ProductExportView

urlpatterns = [
    path("reports/export/orders/", OrderExportView.as_view(), name="report-export-orders"),
    path("reports/export/products/", ProductExportView.as_view(), name="report-export-products"),
    path("reports/export/customers/", CustomerExportView.as_view(), name="report-export-customers"),
]
