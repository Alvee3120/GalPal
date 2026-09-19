"""
Minimal SMS backend interface (email uses Django's own pluggable EMAIL_BACKEND).

    from apps.core.messaging import send_sms
    send_sms("01712345678", "Your GalPal code is 123456")

Pick the backend with `settings.SMS_BACKEND`:
    NullSMSBackend      drops messages (default; safe until a provider is configured)
    ConsoleSMSBackend   prints to the console (dev)
    LocMemSMSBackend    stores in `LocMemSMSBackend.outbox` (tests)
A real provider = subclass `SMSBackend`, implement `send`, point the setting at it.
Module 16 builds templates, Celery retries and NotificationLog on top of this.
"""

import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SMSBackend:
    def send(self, phone, message):
        raise NotImplementedError


class NullSMSBackend(SMSBackend):
    def send(self, phone, message):
        # Never log the message: it may contain a one-time code.
        logger.warning("SMS not sent: no SMS provider configured (SMS_BACKEND).")


class ConsoleSMSBackend(SMSBackend):
    def send(self, phone, message):
        print(f"\n--- SMS to {phone} ---\n{message}\n---------------------\n", flush=True)


class LocMemSMSBackend(SMSBackend):
    outbox = []

    def send(self, phone, message):
        self.outbox.append({"to": phone, "message": message})


def send_sms(phone, message):
    return import_string(settings.SMS_BACKEND)().send(phone, message)
