from django.apps import AppConfig


class DiscountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.discounts"
    verbose_name = "Discounts"

    def ready(self):
        from . import signals  # noqa: F401 - keeps the live-discount index fresh
