import factory

from apps.coupons.models import Coupon, CouponType, CouponUsage


class CouponFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Coupon
        skip_postgeneration_save = True

    code = factory.Sequence(lambda n: f"SAVE{n}")
    type = CouponType.FLAT
    amount = "100.00"
    is_active = True

    @factory.post_generation
    def _reload(obj, create, extracted, **kwargs):
        # Factories hand back the raw values they were given ("100.00" as a str); reload so the
        # instance holds what the database would (Decimal), exactly as production code sees it.
        if create:
            obj.refresh_from_db()


class CouponUsageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CouponUsage
        skip_postgeneration_save = True

    coupon = factory.SubFactory(CouponFactory)
    phone = factory.Sequence(lambda n: f"017{n:08d}")
    order_reference = factory.Sequence(lambda n: f"ORD-{n:05d}")
    discount_amount = "100.00"

    @factory.post_generation
    def _reload(obj, create, extracted, **kwargs):
        if create:
            obj.refresh_from_db()
