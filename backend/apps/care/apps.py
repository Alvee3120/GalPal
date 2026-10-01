from django.apps import AppConfig


class CareConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.care"
    verbose_name = "Customer care"

    def ready(self):
        from . import signals  # noqa: F401 - marks abandoned checkouts converted when an order is placed
