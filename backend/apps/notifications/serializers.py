from rest_framework import serializers

from .models import Channel, Event, NotificationLog


class NotificationLogSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_display", read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True, default=None)

    class Meta:
        model = NotificationLog
        fields = [
            "id", "event", "event_label", "channel", "recipient", "subject", "body", "has_secret", "status", "attempts",
            "error", "sent_at", "created_at", "order", "order_number",
        ]
        read_only_fields = fields


class TemplateSerializer(serializers.Serializer):
    """One event + channel: the text in use (the Admin's, or the built-in default) and what it may contain."""

    event = serializers.ChoiceField(choices=Event.choices)
    event_label = serializers.CharField()
    channel = serializers.ChoiceField(choices=Channel.choices)
    subject = serializers.CharField(allow_blank=True)
    body = serializers.CharField()
    is_active = serializers.BooleanField()
    is_custom = serializers.BooleanField(help_text="False = the built-in default text.")
    placeholders = serializers.ListField(child=serializers.CharField())
    secret_placeholder = serializers.CharField(allow_null=True, help_text="Masked in the log; must stay in the text.")
    default_subject = serializers.CharField(allow_blank=True)
    default_body = serializers.CharField()


class TemplateInputSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    body = serializers.CharField(max_length=5000)
    is_active = serializers.BooleanField(default=True)
