"""
Production settings.

Refuses to start with a missing SECRET_KEY / ALLOWED_HOSTS. Full hardening
(throttling, `check --deploy` clean-up, CSP...) is finished in Module 18.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, MIDDLEWARE, SECRET_KEY, STORAGES, env

DEBUG = False

if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable is required in production.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS environment variable is required in production.")

# Hashed, compressed static files served by WhiteNoise (run `collectstatic` on deploy).
# (Dev and tests use Django's own staticfiles handling, so it is only wired in here.)
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STORAGES["staticfiles"] = {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}

# --- HTTPS / cookies --------------------------------------------------------
# TLS is normally terminated by a reverse proxy that sets X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
