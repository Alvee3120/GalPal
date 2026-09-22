from rest_framework import serializers

from .models import TrackingDestination, TrackingEventLog, TrackingEventName

# Purchase is server-only/automatic (see signals.py) — the frontend never posts it itself.
FRONTEND_EVENT_CHOICES = [c for c in TrackingEventName.choices if c[0] != TrackingEventName.PURCHASE]


class TrackEventSerializer(serializers.Serializer):
    event_name = serializers.ChoiceField(choices=FRONTEND_EVENT_CHOICES)
    event_id = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="Also used for the browser pixel, so Meta can dedupe the two.")
    product_id = serializers.IntegerField(required=False, min_value=1)
    value = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    fbp = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="The _fbp cookie, if present.")
    fbc = serializers.CharField(max_length=100, required=False, allow_blank=True, help_text="The _fbc cookie, if present.")
    event_source_url = serializers.CharField(max_length=500, required=False, allow_blank=True)


class _PersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()


class TrackingEventLogSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.number", read_only=True, default=None)
    user = serializers.SerializerMethodField()

    class Meta:
        model = TrackingEventLog
        fields = [
            "id", "event_name", "destination", "event_id", "order", "order_number", "user", "is_manual_order",
            "request_payload", "response_status", "response_body", "success", "error_message", "attempt", "created_at",
        ]

    def get_user(self, obj) -> dict | None:
        return None if obj.user_id is None else {"id": obj.user_id, "full_name": obj.user.full_name}
