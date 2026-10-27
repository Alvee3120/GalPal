from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="discount",
            name="kind",
            field=models.CharField(
                choices=[
                    ("percentage", "Percentage"),
                    ("fixed", "Fixed amount"),
                    ("buy_x_get_y_percent", "Buy X items, get Y% off"),
                    ("buy_x_get_y_free", "Buy X, get Y free"),
                    ("lowest_free", "Buy X, get the lowest-priced item free"),
                    ("three_for_two", "3 for 2"),
                    ("bundle_price", "Buy X products for a fixed price"),
                ],
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="discount",
            name="value",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Percent (0–100] or taka off, depending on `kind`. Only used by the percentage / fixed product kinds.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="min_quantity",
            field=models.PositiveIntegerField(
                blank=True, help_text="X: how many eligible units are needed to form one offer group.", null=True
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="percent_off",
            field=models.DecimalField(
                blank=True, decimal_places=2, help_text="Y% off, for 'Buy X items, get Y% off'.", max_digits=5, null=True
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="free_quantity",
            field=models.PositiveIntegerField(blank=True, help_text="Y, for 'Buy X, get Y free'.", null=True),
        ),
        migrations.AddField(
            model_name="discount",
            name="bundle_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="৳Y: the total payable price of one group of X eligible products.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="same_product_group",
            field=models.BooleanField(
                default=False,
                help_text="Free units must come from the same eligible product (variant) as the paid ones.",
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="allow_repeat",
            field=models.BooleanField(
                default=True, help_text="Apply the offer once per complete group (off = only the first group counts)."
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="priority",
            field=models.PositiveIntegerField(
                default=100, help_text="Lower runs first when two cart promotions compete for the same units."
            ),
        ),
        migrations.RemoveConstraint(model_name="discount", name="discount_value_positive"),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ["percentage", "fixed"]), _negated=True) | models.Q(("value__gt", 0)),
                name="discount_value_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind", "buy_x_get_y_percent"), _negated=True)
                | (models.Q(("percent_off__gt", 0)) & models.Q(("percent_off__lte", 100))),
                name="discount_percent_off_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("kind__in", ["buy_x_get_y_percent", "buy_x_get_y_free", "lowest_free", "bundle_price"]), _negated=True
                )
                | models.Q(("min_quantity__gte", 1)),
                name="discount_min_quantity_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind", "buy_x_get_y_free"), _negated=True)
                | models.Q(("free_quantity__gte", 1)),
                name="discount_free_quantity_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind", "bundle_price"), _negated=True) | models.Q(("bundle_price__gt", 0)),
                name="discount_bundle_price_positive",
            ),
        ),
    ]
