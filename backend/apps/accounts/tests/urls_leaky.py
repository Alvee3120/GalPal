"""A deliberately misconfigured admin URL conf, used to prove the route sweep catches leaks."""
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsAdminOrCCE


def make_view(permission):
    class View(APIView):
        permission_classes = [permission]

        def get(self, request, *args, **kwargs):
            return Response({"ok": True})

    return View.as_view()


urlpatterns = [
    path("api/v1/admin/safe/", make_view(IsAdmin)),
    path("api/v1/admin/products/", make_view(IsAdminOrCCE)),  # CCE must NOT be able to reach this
    path("api/v1/admin/reports/", make_view(AllowAny)),  # nor this
    path("api/v1/admin/orders/", make_view(IsAdminOrCCE)),  # CCE may reach this one
]
