"""Celery task that delivers one logged notification, retrying with back-off. Without Redis it runs inline."""
from celery import shared_task
from django.conf import settings

from . import services
from .models import LogStatus, NotificationLog


@shared_task(bind=True, max_retries=None)
def deliver_notification(self, log_id):
    log = NotificationLog.objects.filter(pk=log_id).first()
    if log is None or log.status in (LogStatus.SENT, LogStatus.FAILED) or log.has_secret:
        return  # sent already, given up, or holds a secret (those are only ever sent inline, never queued)
    if self.request.is_eager:
        services._deliver_inline(log)  # no broker: all attempts now
        return
    if not services.attempt(log) and log.status == LogStatus.RETRYING:
        base = getattr(settings, "NOTIFICATION_RETRY_SECONDS", 60)
        raise self.retry(countdown=base * 2 ** (log.attempts - 1))
