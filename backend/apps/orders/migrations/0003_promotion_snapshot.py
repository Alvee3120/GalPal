import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_invoice_layout_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="promotion_discount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Automatic cart-promotion discount (apps.discounts), separate from the coupon's `discount_amount`.",
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="applied_promotions",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Snapshot of the cart promotions applied at order time, so later edits never rewrite history.",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="promotion_discount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Promotion discount allocated to this line (0 for none). Sums to the order's `promotion_discount`.",
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="free_quantity",
            field=models.PositiveIntegerField(default=0, help_text="Units of this line that were free under a promotion."),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.CheckConstraint(
                condition=models.Q(("subtotal__gte", models.F("discount_amount") + models.F("promotion_discount"))),
                name="order_discounts_lte_subtotal",
            ),
        ),
    ]
