"""
Production settings.

Refuses to start with a missing SECRET_KEY / ALLOWED_HOSTS. `python manage.py check --deploy` is clean with these
settings (Module 18); API security headers are added in every environment by apps.core.middleware.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, MIDDLEWARE, REST_FRAMEWORK, SECRET_KEY, STORAGES, env

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
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
# Behind the reverse proxy the client IP is the first X-Forwarded-For hop (audit log / throttles); only trust it when
# the proxy overwrites that header.
AUDIT_TRUST_X_FORWARDED_FOR = env.bool("TRUST_X_FORWARDED_FOR", default=False)
# Per-IP throttles: with N trusted proxies in front, DRF reads the client IP from X-Forwarded-For (else every
# visitor would share the proxy's IP and one abuser could throttle everyone).
if env("NUM_PROXIES", default=""):
    REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env.int("NUM_PROXIES")}

# HSTS subdomains/preload are long-term commitments that can lock out an HTTP-only subdomain: switched on through the
# environment once every subdomain is HTTPS (SECURE_HSTS_INCLUDE_SUBDOMAINS), not by default.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
