"""Shared serializers, mostly used to document responses in OpenAPI."""

from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):
    status = serializers.IntegerField(help_text="HTTP status code.")
    code = serializers.CharField(help_text="Stable machine-readable error code.")
    message = serializers.CharField(help_text="Human-readable summary.")
    details = serializers.JSONField(
        allow_null=True,
        help_text="Field errors (validation), `{retry_after}` (throttling) or null.",
    )


class ErrorResponseSerializer(serializers.Serializer):
    """The envelope returned by every error response."""

    error = ErrorDetailSerializer()


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    service = serializers.CharField()
    version = serializers.CharField()
    time = serializers.DateTimeField()
    checks = serializers.DictField(
        child=serializers.CharField(), help_text="Per-dependency result: `ok` or `error`."
    )
