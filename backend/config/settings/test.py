"""Settings used by pytest: dev settings tuned for speed and isolation."""

import tempfile

from .dev import *  # noqa: F401,F403

DEBUG = False

# Fast hashing keeps auth-heavy tests quick.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Never write uploads into the real media directory.
MEDIA_ROOT = tempfile.mkdtemp(prefix="galpal-test-media-")

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Capture SMS in memory (`apps.core.messaging.LocMemSMSBackend.outbox`); pytest-django
# already swaps Django's email backend for the in-memory one.
SMS_BACKEND = "apps.core.messaging.LocMemSMSBackend"
