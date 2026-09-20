from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"

    def ready(self):
        from django.db import models
        from rest_framework.serializers import ModelSerializer

        from .serializers import BooleanField

        # Project-wide fix, not per-serializer: see BooleanField's docstring. Patched once here so
        # every ModelSerializer (present and future, this app or the next) gets it automatically.
        ModelSerializer.serializer_field_mapping[models.BooleanField] = BooleanField
