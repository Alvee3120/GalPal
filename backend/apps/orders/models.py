from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.catalog.models import Product, ProductVariant
from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.coupons.models import Coupon
from apps.shipping.models import DeliveryMethod, DeliveryZone

_min_zero = MinValueValidator(Decimal("0"))


class OrderSource(models.TextChoices):
    """Where an order came from. Storefront checkout is always `website`; staff pick the rest."""

    WEBSITE = "website", "Website"
    FACEBOOK = "facebook", "Facebook"
    INSTAGRAM = "instagram", "Instagram"
    TIKTOK = "tiktok", "TikTok"
    WHATSAPP = "whatsapp", "WhatsApp"
    MESSENGER = "messenger", "Messenger"
    CALL = "call", "Phone call"
    OTHER = "other", "Other"


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    PROCESSING = "processing", "Processing"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"
    RETURNED = "returned", "Returned"
    FAILED = "failed", "Failed"


class PaymentMethod(models.TextChoices):
    COD = "cod", "Cash on delivery"
    ONLINE = "online", "Online payment"


class PaymentStatus(models.TextChoices):
    """Owned by Module 11 (Payments); orders only carry the current value and never edit it."""

    UNPAID = "unpaid", "Unpaid"
    PAID = "paid", "Paid"
    PARTIALLY_PAID = "partially_paid", "Partially paid"
    REFUNDED = "refunded", "Refunded"
    FAILED = "failed", "Failed"


class Order(TimeStampedModel, SoftDeleteModel):
    """
    One placed order. Everything a customer saw or a rider needs is *copied* onto it (contact,
    address, item names/prices, the shipping zone and charge, tax %, coupon code) so later edits to
    the catalog, zones or coupons can never rewrite history. The foreign keys to zone, delivery
    method, coupon, customer and staff are SET_NULL for the same reason: deleting one leaves the
    order intact, with its copied values.

    `shipping_zone` / `delivery_method` use `related_name="orders"`: Module 9's "a zone that has
    orders can't be deleted" guard finds orders through that name.
    """

    number = models.CharField(max_length=20, unique=True, help_text="Human-readable and not guessable, e.g. GP-260921-7K3F")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")

    # Contact + delivery address, as they were when the order was placed / last edited.
    customer_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=11, db_index=True)
    email = models.EmailField(blank=True)
    division = models.CharField(max_length=60, blank=True)
    district = models.CharField(max_length=60)
    area = models.CharField(max_length=100, blank=True)
    address_line = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=10, blank=True)
    note = models.TextField(blank=True, help_text="The customer's note for delivery")

    source = models.CharField(max_length=12, choices=OrderSource.choices, db_index=True)
    source_note = models.CharField(max_length=255, blank=True)
    is_manual = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    status = models.CharField(max_length=12, choices=OrderStatus.choices, default=OrderStatus.PENDING, db_index=True)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, validators=[_min_zero])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[_min_zero])
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    coupon_code = models.CharField(max_length=32, blank=True)

    shipping_zone = models.ForeignKey(DeliveryZone, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    shipping_zone_name = models.CharField(max_length=80, blank=True)
    delivery_method = models.ForeignKey(DeliveryMethod, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    delivery_method_name = models.CharField(max_length=60, blank=True)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[_min_zero])
    shipping_free_reason = models.CharField(max_length=30, blank=True)
    shipping_overridden = models.BooleanField(default=False)
    shipping_override_reason = models.CharField(max_length=255, blank=True)

    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[_min_zero])
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, validators=[_min_zero])

    # Courier hooks (Pathao / Steadfast later); plain text for now.
    courier_name = models.CharField(max_length=60, blank=True)
    tracking_id = models.CharField(max_length=100, blank=True)
    consignment_id = models.CharField(max_length=100, blank=True)

    stock_released_at = models.DateTimeField(null=True, blank=True, help_text="Set once the order's stock has been put back.")
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True, help_text="Hash of phone + items, for duplicate detection.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["source", "-created_at"]),
            models.Index(fields=["customer", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="order_subtotal_gte_0"),
            models.CheckConstraint(condition=Q(discount_amount__gte=0), name="order_discount_gte_0"),
            models.CheckConstraint(condition=Q(discount_amount__lte=models.F("subtotal")), name="order_discount_lte_subtotal"),
            models.CheckConstraint(condition=Q(shipping_charge__gte=0), name="order_shipping_gte_0"),
            models.CheckConstraint(condition=Q(tax_amount__gte=0), name="order_tax_gte_0"),
            models.CheckConstraint(condition=Q(grand_total__gte=0), name="order_grand_total_gte_0"),
        ]

    def __str__(self):
        return self.number

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    """A line of an order: a frozen copy of what was bought and at what price."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="order_items")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL, related_name="order_items")

    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=64)
    variant_label = models.CharField(max_length=200, blank=True, help_text='e.g. "Shade: Rose / Size: 50ml"')
    image = models.CharField(max_length=500, blank=True, help_text="Storage path of the image at order time")
    regular_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[_min_zero])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[_min_zero])
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    line_total = models.DecimalField(max_digits=12, decimal_places=2, validators=[_min_zero])
    stock_deducted = models.PositiveIntegerField(default=0, help_text="Units actually taken from stock (0 if stock isn't managed).")

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=1), name="order_item_quantity_gte_1")]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


class OrderStatusHistory(models.Model):
    """Append-only: one row per status change (and per shipping override / edit), with who and why."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12, choices=OrderStatus.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name_plural = "order status history"

    def __str__(self):
        return f"{self.order_id}: {self.from_status or '-'} -> {self.to_status}"


class OrderNote(models.Model):
    """An internal note by staff. Never shown to the customer."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Note on {self.order_id}"
