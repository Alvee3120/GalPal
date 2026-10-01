from rest_framework import serializers

from apps.orders.models import Order

from .models import (
    CheckoutLead,
    CheckoutLeadStatus,
    ContactMessage,
    ContactMessageNote,
    CustomerNote,
    CustomerTag,
    MessageStatus,
    ReturnReason,
    ReturnRequest,
    ReturnStatus,
)


class CareStaffRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()


# --- public / customer ---------------------------------------------------------------------------------------------------


class ContactMessageInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    subject = serializers.CharField(max_length=150, required=False, allow_blank=True)
    message = serializers.CharField(max_length=5000)


class CheckoutLeadInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20)
    email = serializers.CharField(max_length=254, required=False, allow_blank=True)
    district = serializers.CharField(max_length=60, required=False, allow_blank=True)


class ReturnRequestInputSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=ReturnReason.choices)
    details = serializers.CharField(max_length=2000)


class CustomerReturnRequestSerializer(serializers.ModelSerializer):
    """What the customer sees about their own request (no staff names)."""

    class Meta:
        model = ReturnRequest
        fields = ["id", "reason", "details", "status", "admin_note", "created_at", "updated_at"]
        read_only_fields = fields


# --- admin -------------------------------------------------------------------------------------------------------------


class CustomerTagSerializer(serializers.ModelSerializer):
    customer_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = CustomerTag
        fields = ["id", "name", "customer_count"]


class CustomerNoteSerializer(serializers.ModelSerializer):
    author = CareStaffRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = CustomerNote
        fields = ["id", "text", "author", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class CareOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "number", "status", "payment_status", "grand_total", "source", "created_at"]
        read_only_fields = fields


class CustomerProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    avatar = serializers.ImageField(allow_null=True)
    is_active = serializers.BooleanField()
    created_via_checkout = serializers.BooleanField()
    date_joined = serializers.DateTimeField(source="created_at")
    last_login = serializers.DateTimeField(allow_null=True)
    stats = serializers.DictField()
    tags = CustomerTagSerializer(many=True)
    notes = CustomerNoteSerializer(many=True)
    recent_orders = CareOrderSerializer(many=True)


class SetTagsSerializer(serializers.Serializer):
    tags = serializers.ListField(child=serializers.CharField(max_length=40), max_length=20, help_text="Tag names; new ones are created")


class NoteInputSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)
    status = serializers.ChoiceField(choices=MessageStatus.choices, required=False)


class ContactMessageNoteSerializer(serializers.ModelSerializer):
    author = CareStaffRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = ContactMessageNote
        fields = ["id", "text", "author", "created_at"]
        read_only_fields = fields


class AdminContactMessageSerializer(serializers.ModelSerializer):
    notes = ContactMessageNoteSerializer(many=True, read_only=True)
    user = CareStaffRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = ContactMessage
        fields = ["id", "name", "phone", "email", "subject", "message", "status", "user", "notes", "created_at", "updated_at"]
        read_only_fields = [f for f in fields if f != "status"]


class AdminCheckoutLeadSerializer(serializers.ModelSerializer):
    user = CareStaffRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = CheckoutLead
        fields = ["id", "name", "phone", "email", "district", "user", "cart_snapshot", "cart_value", "status", "created_at", "updated_at"]
        read_only_fields = [f for f in fields if f != "status"]

    def validate_status(self, value):
        if value == CheckoutLeadStatus.CONVERTED:
            raise serializers.ValidationError("A checkout is marked Ordered automatically when its order is placed.")
        return value


class AdminReturnRequestSerializer(serializers.ModelSerializer):
    order = CareOrderSerializer(read_only=True)
    customer = serializers.SerializerMethodField()
    handled_by = CareStaffRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = ReturnRequest
        fields = ["id", "order", "customer", "reason", "details", "status", "admin_note", "handled_by", "created_at", "updated_at"]
        read_only_fields = ["id", "order", "customer", "reason", "details", "handled_by", "created_at", "updated_at"]

    def get_customer(self, obj) -> dict:
        return {"id": obj.customer_id, "full_name": obj.customer.full_name, "phone": obj.customer.phone}

    def validate_status(self, value):
        if value not in ReturnStatus.values:
            raise serializers.ValidationError("Unknown status.")
        return value
