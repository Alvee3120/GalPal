"""Regression test: DRF's BooleanField treats an absent multipart field as False (HTML checkbox
semantics), silently overriding a model's `default=True`. apps.core.apps.CoreConfig.ready()
patches every ModelSerializer's BooleanField to avoid this. See apps/core/serializers.py."""
import pytest
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.catalog.models import Product
from apps.catalog.serializers import AdminCategorySerializer
from apps.catalog.serializers_product import AdminProductSerializer

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


def as_multipart_request(data):
    return Request(factory.post("/x", data, format="multipart"), parsers=[MultiPartParser()])


def test_omitted_boolean_falls_back_to_the_model_default_on_multipart():
    serializer = AdminCategorySerializer(data=as_multipart_request({"name": "X"}).data)
    assert serializer.is_valid(), serializer.errors
    assert "is_active" not in serializer.validated_data  # let the model default (True) apply


def test_explicitly_sent_false_is_still_respected_on_multipart():
    serializer = AdminCategorySerializer(data=as_multipart_request({"name": "X", "is_active": "false"}).data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["is_active"] is False


def test_manage_stock_defaults_to_true_when_creating_a_product_via_multipart(auth_client, admin_user):
    from apps.catalog.tests.factories import make_image

    response = auth_client(admin_user).post(
        "/api/v1/admin/products/",
        {"name": "X", "sku": "MP-1", "regular_price": "10.00", "feature_image": make_image()},
        format="multipart",
    )
    assert response.status_code == 201
    assert response.json()["manage_stock"] is True
    assert Product.objects.get(sku="MP-1").manage_stock is True
