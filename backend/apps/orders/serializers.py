from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.conf import settings
from rest_framework import serializers

from apps.accounts.models import Address, User
from apps.core.validators import normalize_bd_phone

from . import services
from .models import Order, OrderItem, OrderNote, OrderSource, OrderStatus, OrderStatusHistory, PaymentMethod


def _phone(value):
    try:
        return normalize_bd_phone(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages[0], code="invalid_phone") from None


def _media_url(request, path):
    if not path:
        return None
    url = default_storage.url(path)
    return request.build_absolute_uri(url) if request is not None and url.startswith("/") else url


def _payment_method(value):
    if value not in settings.ENABLED_PAYMENT_METHODS:
        raise serializers.ValidationError("This payment method is not available.", code="payment_method_unavailable")
    return value


# --- input: checkout (storefront) ---------------------------------------------------------------------------


class AddressInputMixin(serializers.Serializer):
    """Contact + delivery address, shared by checkout, manual orders and order edits."""

    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True)
    division = serializers.CharField(max_length=60, required=False, allow_blank=True)
    district = serializers.CharField(max_length=60, help_text="Decides the delivery zone and charge.")
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="Thana / upazila / area")
    address_line = serializers.CharField(max_length=255)
    postal_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    delivery_method = serializers.CharField(max_length=80, required=False, allow_blank=True, help_text="Slug of an active delivery method; blank = none.")

    def validate_phone(self, value):
        return _phone(value)

    def validate_email(self, value):
        return value.strip().lower()


class CheckoutSerializer(AddressInputMixin):
    """
    What the storefront may send. Deliberately absent: `source` (always `website`), the shipping charge
    and zone (computed), prices, totals and the customer. Unknown keys are ignored.
    """

    coupon = serializers.CharField(max_length=32, required=False, allow_blank=True, help_text="Optional; blank uses the coupon already applied to the cart.")
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.COD)
    save_details = serializers.BooleanField(
        default=False,
        help_text="Guests only: also create an account from these details (needs a valid email). Ignored for logged-in customers.",
    )

    def validate_payment_method(self, value):
        return _payment_method(value)


# --- input: manual orders and edits (staff) ---------------------------------------------------------------------


class OrderLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    variant_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class ManualOrderSerializer(AddressInputMixin):
    items = OrderLineInputSerializer(many=True, allow_empty=False, max_length=100)
    source = serializers.ChoiceField(choices=OrderSource.choices, help_text="Required: where this order came from.")
    source_note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    coupon = serializers.CharField(max_length=32, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.COD)
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=User.objects.filter(role=User.Role.CUSTOMER, is_active=True), required=False, allow_null=True,
        help_text="Link the order to an existing customer (from the phone lookup). Omit for a guest order.",
    )

    def validate_payment_method(self, value):
        return _payment_method(value)


class OrderUpdateSerializer(serializers.Serializer):
    """PATCH of a pending order. Send only what changes; `items` replaces the whole item list."""

    name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    division = serializers.CharField(max_length=60, required=False, allow_blank=True)
    district = serializers.CharField(max_length=60, required=False)
    area = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address_line = serializers.CharField(max_length=255, required=False)
    postal_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    delivery_method = serializers.CharField(max_length=80, required=False, allow_blank=True)
    items = OrderLineInputSerializer(many=True, required=False, allow_empty=False, max_length=100)
    remove_coupon = serializers.BooleanField(required=False, help_text="Drop the order's coupon (needed if it no longer applies).")

    def validate_phone(self, value):
        return _phone(value)

    def validate_email(self, value):
        return value.strip().lower()

    def service_data(self):
        """validated_data with the API's `name` mapped to the model's `customer_name`."""
        data = dict(self.validated_data)
        if "name" in data:
            data["customer_name"] = data.pop("name")
        return data


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    courier_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    tracking_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    consignment_id = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ShippingOverrideSerializer(serializers.Serializer):
    charge = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField(max_length=255, help_text="Required. Recorded in the order's history.")


class TrackOrderSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=20)
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        return _phone(value)


class CancelOrderSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


# --- output: shared -------------------------------------------------------------------------------------------------


class OrderItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id", "product_id", "variant_id", "product_name", "sku", "variant_label", "image",
            "regular_price", "unit_price", "quantity", "line_total",
        ]

    def get_image(self, obj) -> str | None:
        return _media_url(self.context.get("request"), obj.image)


class PublicHistorySerializer(serializers.ModelSerializer):
    """What a customer sees of the timeline: the status and when. No staff names, no internal notes."""

    status = serializers.CharField(source="to_status")

    class Meta:
        model = OrderStatusHistory
        fields = ["status", "created_at"]


_MONEY_AND_SHIPPING = [
    "subtotal", "discount_amount", "coupon_code", "shipping_zone_name", "delivery_method_name", "shipping_charge",
    "shipping_free_reason", "tax_percent", "tax_amount", "grand_total",
]
_ADDRESS = ["customer_name", "phone", "division", "district", "area", "address_line", "postal_code", "note"]


class OrderListSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["number", "status", "payment_method", "payment_status", "item_count", "grand_total", "created_at"]

    def get_item_count(self, obj) -> int:
        return obj.item_count


class PublicOrderSerializer(serializers.ModelSerializer):
    """A customer's (or a tracking guest's) view of an order. No source, staff, notes, IP or fingerprint."""

    items = OrderItemSerializer(many=True, read_only=True)
    history = PublicHistorySerializer(many=True, read_only=True)
    can_cancel = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "number", "status", "payment_method", "payment_status", "email", *_ADDRESS, "items", "item_count",
            *_MONEY_AND_SHIPPING, "courier_name", "tracking_id", "consignment_id", "can_cancel", "history", "created_at",
        ]

    def get_can_cancel(self, obj) -> bool:
        return obj.status in services.CUSTOMER_CANCELLABLE

    def get_item_count(self, obj) -> int:
        return obj.item_count


class TrackedOrderSerializer(PublicOrderSerializer):
    """The guest tracking view: number + phone is a weak credential, so the email is left out."""

    class Meta(PublicOrderSerializer.Meta):
        fields = [f for f in PublicOrderSerializer.Meta.fields if f != "email"]


class CheckoutResultSerializer(serializers.Serializer):
    order = PublicOrderSerializer()
    account_created = serializers.BooleanField(help_text="True if an account was created from the checkout details. Never carries credentials.")


# --- output: staff -------------------------------------------------------------------------------------------------------


class _PersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()


class StaffHistorySerializer(serializers.ModelSerializer):
    changed_by = _PersonSerializer(read_only=True, allow_null=True)

    class Meta:
        model = OrderStatusHistory
        fields = ["id", "from_status", "to_status", "changed_by", "note", "created_at"]


class OrderNoteSerializer(serializers.ModelSerializer):
    author = _PersonSerializer(read_only=True, allow_null=True)

    class Meta:
        model = OrderNote
        fields = ["id", "text", "author", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class StaffOrderListSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    created_by = _PersonSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = [
            "id", "number", "status", "source", "is_manual", "customer_name", "phone", "district", "payment_method",
            "payment_status", "item_count", "grand_total", "shipping_charge", "created_by", "created_at",
        ]

    def get_item_count(self, obj) -> int:
        return obj.item_count


class StaffOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    history = StaffHistorySerializer(many=True, read_only=True)
    notes = OrderNoteSerializer(many=True, read_only=True)
    customer = _PersonSerializer(read_only=True, allow_null=True)
    created_by = _PersonSerializer(read_only=True, allow_null=True)
    allowed_transitions = serializers.SerializerMethodField()
    editable = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "number", "status", "allowed_transitions", "editable", "source", "source_note", "is_manual", "created_by",
            "customer", "email", *_ADDRESS, "payment_method", "payment_status", "items", "item_count", *_MONEY_AND_SHIPPING,
            "shipping_overridden", "shipping_override_reason", "courier_name", "tracking_id", "consignment_id",
            "ip_address", "history", "notes", "created_at", "updated_at",
        ]

    def get_allowed_transitions(self, obj) -> list[str]:
        return services.allowed_transitions(obj.status)

    def get_editable(self, obj) -> bool:
        return obj.status == OrderStatus.PENDING

    def get_item_count(self, obj) -> int:
        return obj.item_count


class ManualOrderResultSerializer(serializers.Serializer):
    order = StaffOrderSerializer()
    warnings = serializers.ListField(child=serializers.CharField(), help_text="e.g. a similar recent order for this phone. The order was still created.")


# --- output: invoice + helpers ---------------------------------------------------------------------------------------------


class _InvoiceParty(serializers.Serializer):
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    address = serializers.CharField(allow_blank=True)


class _InvoiceLine(serializers.Serializer):
    name = serializers.CharField()
    sku = serializers.CharField()
    variant = serializers.CharField(allow_blank=True)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2)


class InvoiceSerializer(serializers.Serializer):
    number = serializers.CharField()
    date = serializers.DateTimeField()
    status = serializers.CharField()
    currency_symbol = serializers.CharField()
    seller = _InvoiceParty()
    bill_to = _InvoiceParty()
    ship_to = _InvoiceParty()
    items = _InvoiceLine(many=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    coupon_code = serializers.CharField(allow_blank=True)
    shipping_zone = serializers.CharField(allow_blank=True)
    shipping_charge = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.CharField()
    payment_status = serializers.CharField()
    note = serializers.CharField(allow_blank=True)


class PickerRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    sku = serializers.CharField()
    variant_label = serializers.CharField(allow_blank=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    stock = serializers.IntegerField(allow_null=True, help_text="null when stock isn't tracked")
    image = serializers.SerializerMethodField()

    def get_image(self, row) -> str | None:
        image = row["image"]
        return _media_url(self.context.get("request"), image.name if image else "")


class ShippingHelperQuerySerializer(serializers.Serializer):
    district = serializers.CharField(max_length=100)
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    delivery_method = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


class _LookupAddress(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["id", "label", "full_name", "phone", "division", "district", "area", "address_line", "postal_code", "is_default"]


class CustomerLookupSerializer(serializers.ModelSerializer):
    addresses = _LookupAddress(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "phone", "addresses"]


def build_invoice(order, site):
    """Print-ready invoice data: everything on the page, all from the order's own snapshot."""
    def party_address(o):
        return ", ".join(p for p in (o.address_line, o.area, o.district, o.division, o.postal_code) if p)

    return {
        "number": order.number, "date": order.created_at, "status": order.status, "currency_symbol": site.currency_symbol,
        "seller": {"name": site.site_name, "phone": site.phone, "email": site.email, "address": site.address},
        "bill_to": {"name": order.customer_name, "phone": order.phone, "email": order.email, "address": party_address(order)},
        "ship_to": {"name": order.customer_name, "phone": order.phone, "email": order.email, "address": party_address(order)},
        "items": [
            {"name": i.product_name, "sku": i.sku, "variant": i.variant_label, "quantity": i.quantity,
             "unit_price": i.unit_price, "line_total": i.line_total}
            for i in order.items.all()
        ],
        "subtotal": order.subtotal, "discount": order.discount_amount, "coupon_code": order.coupon_code,
        "shipping_zone": order.shipping_zone_name, "shipping_charge": order.shipping_charge,
        "tax_percent": order.tax_percent, "tax_amount": order.tax_amount, "grand_total": order.grand_total,
        "payment_method": order.get_payment_method_display(), "payment_status": order.get_payment_status_display(),
        "note": order.note,
    }
