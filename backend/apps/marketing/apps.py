from django.apps import AppConfig


class MarketingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.marketing"
    label = "marketing"
    verbose_name = "Marketing & Tracking"

    def ready(self):
        from . import signals  # noqa: F401
