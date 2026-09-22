"""Importing the Celery app here makes `@shared_task` decorated functions register with it as
soon as Django starts, whichever settings module is active."""
from .celery import app as celery_app

__all__ = ["celery_app"]
