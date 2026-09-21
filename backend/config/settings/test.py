"""Settings used by pytest: dev settings tuned for speed and isolation."""

import tempfile

from .base import env
from .dev import *  # noqa: F401,F403

DEBUG = False

# --- Isolation from shared cloud resources -----------------------------------------------------
# The team may point DATABASE_URL / USE_S3 at a shared cloud Postgres and an R2 bucket in their
# .env. The test suite must never touch those: it creates and drops a database and uploads and
# deletes files. So tests always get a *local* database (override with TEST_DATABASE_URL) and
# always use throwaway local file storage, whatever .env says.
DATABASES = {
    "default": {
        **env.db("TEST_DATABASE_URL", default="postgres://galpal:galpal@localhost:5432/galpal"),
        "CONN_MAX_AGE": 0,
        "ATOMIC_REQUESTS": False,
    }
}
USE_S3 = False
# Blank every cloud setting too: django-storages falls back to these globals for any option a
# STORAGES entry leaves out, so a stray endpoint here would send "mocked" S3 traffic to real R2.
AWS_ACCESS_KEY_ID = AWS_SECRET_ACCESS_KEY = AWS_STORAGE_BUCKET_NAME = None
AWS_S3_ENDPOINT_URL = AWS_S3_CUSTOM_DOMAIN = AWS_S3_REGION_NAME = None
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Fast hashing keeps auth-heavy tests quick.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Never write uploads into the real media directory.
MEDIA_ROOT = tempfile.mkdtemp(prefix="galpal-test-media-")

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Capture SMS in memory (`apps.core.messaging.LocMemSMSBackend.outbox`); pytest-django
# already swaps Django's email backend for the in-memory one.
SMS_BACKEND = "apps.core.messaging.LocMemSMSBackend"
