from django.apps import AppConfig


class BannersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.banners"
    label = "banners"
    verbose_name = "Hero Banners"

    def ready(self):
        from . import signals  # noqa: F401
