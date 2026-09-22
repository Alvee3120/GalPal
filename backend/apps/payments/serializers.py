from decimal import Decimal

from rest_framework import serializers

from . import services
from .models import Payment, Refund


class RefundSerializer(serializers.ModelSerializer):
    processed_by = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = ["id", "amount", "reason", "status", "transaction_id", "processed_by", "created_at"]

    def get_processed_by(self, obj) -> dict | None:
        return None if obj.processed_by_id is None else {"id": obj.processed_by_id, "full_name": obj.processed_by.full_name}


class _PersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.number", read_only=True)
    net_received = serializers.SerializerMethodField()
    refunded_amount = serializers.SerializerMethodField()
    collected_by = serializers.SerializerMethodField()
    refunds = RefundSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "order", "order_number", "method", "gateway", "status", "amount", "amount_received",
            "net_received", "refunded_amount", "transaction_id", "gateway_payload", "collected_by", "note",
            "refunds", "created_at", "updated_at",
        ]

    def get_net_received(self, obj) -> str:
        return str(services.net_received(obj))

    def get_refunded_amount(self, obj) -> str:
        return str(services.refunded_total(obj))

    def get_collected_by(self, obj) -> dict | None:
        return None if obj.collected_by_id is None else {"id": obj.collected_by_id, "full_name": obj.collected_by.full_name}


class PaymentListSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "order", "order_number", "method", "gateway", "status", "amount", "amount_received", "created_at"]


# --- admin actions --------------------------------------------------------------------------------------


class MarkReceivedSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal("0.01"), help_text="Defaults to whatever is still owed.")
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class InitiatePaymentSerializer(serializers.Serializer):
    gateway = serializers.CharField(max_length=30, required=False, help_text="Defaults to settings.DEFAULT_PAYMENT_GATEWAY.")


class InitiateResultSerializer(serializers.Serializer):
    reference = serializers.CharField()
    redirect_url = serializers.CharField()


class RefundInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(max_length=255)
    transaction_id = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="The gateway's refund id, if it was processed there.")
