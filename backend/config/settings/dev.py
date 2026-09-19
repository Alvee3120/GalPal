"""Local development settings."""

from .base import *  # noqa: F401,F403
from .base import CORS_ALLOWED_ORIGINS, SECRET_KEY, env

DEBUG = env.bool("DEBUG", default=True)

if not SECRET_KEY:
    SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"  # noqa: S105

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]", "testserver"])

# The Next.js dev server
if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
