"""
The Celery app. Autodiscovers `tasks.py` in every installed app (currently just
`apps.marketing`), so a future module (Module 16's emails/SMS, abandoned-cart reminders) that adds
its own `tasks.py` needs no change here.

Uses the same Redis the cache does (`REDIS_URL`) as both broker and result backend — there's no
separate Celery-specific Redis instance to run in dev. Without `REDIS_URL` set (a bare local dev
box with no Redis), `CELERY_TASK_ALWAYS_EAGER` runs tasks synchronously in-process instead of
silently queuing them nowhere; see settings for exactly when that applies.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("galpal")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
