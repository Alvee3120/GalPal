from django.apps import AppConfig


class SiteSettingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.site_settings"
    label = "site_settings"
    verbose_name = "Site settings"

    def ready(self):
        from . import signals  # noqa: F401
