"""URL conf used only by the core tests: views that raise every kind of error."""
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.urls import include, path
from rest_framework import exceptions, serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class _Open(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


class Protected(APIView):
    """Uses the project defaults: JWT auth + IsAuthenticated."""

    def get(self, request):
        return Response({"ok": True})


class DrfValidation(_Open):
    class S(serializers.Serializer):
        phone = serializers.CharField()
        qty = serializers.IntegerField(min_value=1)

    def post(self, request):
        s = self.S(data=request.data)
        s.is_valid(raise_exception=True)


class ListValidation(_Open):
    def get(self, request):
        raise exceptions.ValidationError(["Something is wrong overall."])


class DjangoValidation(_Open):
    def get(self, request):
        raise DjangoValidationError({"sku": ["Duplicate SKU."]})


class Forbidden(_Open):
    def get(self, request):
        raise exceptions.PermissionDenied("Admins only.")


class DjangoForbidden(_Open):
    def get(self, request):
        raise PermissionDenied()


class DjangoNotFound(_Open):
    def get(self, request):
        raise Http404()


class ThrottledView(_Open):
    def get(self, request):
        raise exceptions.Throttled(wait=30)


class ConflictWithDetails(exceptions.APIException):
    status_code = 409
    default_code = "in_use"
    default_detail = "It is in use."
    details = {"children_count": 3}


class ConflictView(_Open):
    def get(self, request):
        raise ConflictWithDetails()


class Boom(_Open):
    def get(self, request):
        raise RuntimeError("secret internal detail")


class Numbers(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    filter_backends = []

    def get(self, request):
        page = self.paginate_queryset(list(range(250)))
        return self.get_paginated_response(page)


urlpatterns = [
    path("protected/", Protected.as_view()),
    path("validation/", DrfValidation.as_view()),
    path("list-validation/", ListValidation.as_view()),
    path("django-validation/", DjangoValidation.as_view()),
    path("forbidden/", Forbidden.as_view()),
    path("django-forbidden/", DjangoForbidden.as_view()),
    path("django-404/", DjangoNotFound.as_view()),
    path("throttled/", ThrottledView.as_view()),
    path("boom/", Boom.as_view()),
    path("conflict/", ConflictView.as_view()),
    path("numbers/", Numbers.as_view()),
    path("api/v1/", include("apps.core.urls")),
]

handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
