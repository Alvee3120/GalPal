from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.coupons.models import CouponUsage

from .factories import CouponFactory, CouponUsageFactory

pytestmark = pytest.mark.django_db


def test_code_is_stored_uppercase_and_stripped():
    coupon = CouponFactory(code="  save10 ")
    coupon.refresh_from_db()
    assert coupon.code == "SAVE10" and str(coupon) == "SAVE10"


def test_code_is_unique_regardless_of_case():
    CouponFactory(code="WELCOME")
    with pytest.raises(IntegrityError), transaction.atomic():
        CouponFactory(code="welcome")


def test_percentage_over_100_is_rejected_by_the_database():
    with pytest.raises(IntegrityError), transaction.atomic():
        CouponFactory(type="percentage", amount="150.00")
    CouponFactory(type="percentage", amount="100.00")  # exactly 100 is fine
    CouponFactory(type="flat", amount="150.00")  # flat may exceed 100


def test_amount_must_be_positive():
    coupon = CouponFactory.build(amount="0.00")
    with pytest.raises(ValidationError):
        coupon.full_clean()


def test_expiry_must_be_after_start_at_db_level():
    now = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        CouponFactory(start_at=now, expiry_at=now)
    CouponFactory(start_at=now, expiry_at=now + timedelta(days=1))


def test_defaults():
    coupon = CouponFactory()
    assert coupon.is_active and coupon.min_order_amount == 0
    assert coupon.total_usage_limit is None and coupon.per_customer_usage_limit is None
    assert not (coupon.exclude_sale_items or coupon.first_order_only or coupon.free_shipping)


def test_applicability_m2ms_start_empty():
    coupon = CouponFactory()
    assert not coupon.products.exists() and not coupon.categories.exists() and not coupon.brands.exists()


# --- usage ------------------------------------------------------------------------------------


def test_a_used_coupon_cannot_be_deleted_at_the_database_level():
    usage = CouponUsageFactory()
    with pytest.raises(Exception) as exc:
        usage.coupon.delete()
    assert "protected" in str(exc.type.__name__).lower() or "protected" in str(exc.value).lower()


def test_same_coupon_cannot_be_redeemed_twice_for_one_order():
    usage = CouponUsageFactory(order_reference="ORD-1")
    with pytest.raises(IntegrityError), transaction.atomic():
        CouponUsageFactory(coupon=usage.coupon, order_reference="ORD-1")


def test_same_order_reference_is_fine_across_different_coupons():
    CouponUsageFactory(order_reference="ORD-1")
    CouponUsageFactory(order_reference="ORD-1")


def test_blank_order_references_do_not_collide():
    coupon = CouponFactory()
    CouponUsageFactory(coupon=coupon, order_reference="")
    CouponUsageFactory(coupon=coupon, order_reference="")


def test_usage_survives_user_deletion_and_keeps_the_phone():
    """Regression: SET_NULL on user must not violate any constraint (phone is always recorded)."""
    user = UserFactory()
    usage = CouponUsageFactory(user=user, phone=user.phone)
    user.delete()
    usage.refresh_from_db()
    assert usage.user is None and usage.phone
    assert CouponUsage.objects.filter(pk=usage.pk).exists()


def test_usage_phone_is_normalised_and_validated():
    usage = CouponUsageFactory.build(phone="12345")
    with pytest.raises(ValidationError):
        usage.full_clean()
