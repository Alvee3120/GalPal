"""
Base settings shared by every environment.

Environment-specific behaviour lives in dev.py / prod.py / test.py. Secrets and
per-deployment values come from environment variables (or backend/.env).
"""

import re
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
from corsheaders.defaults import default_headers

# backend/ (the directory containing manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    # Real environment variables always win over values in .env
    environ.Env.read_env(str(_env_file))

# --- Core -------------------------------------------------------------------

# Empty by default: dev.py supplies an insecure key, prod.py refuses to boot without one.
SECRET_KEY = env("SECRET_KEY", default="")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

APP_NAME = "GalPal API"
APP_VERSION = env("APP_VERSION", default="0.1.0")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    # Local
    "apps.core",
    "apps.accounts",
    "apps.site_settings",
    "apps.catalog",
    "apps.banners",
    "apps.videos",
    "apps.cart",
    "apps.coupons",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Only needed for the Django admin fallback and the Swagger UI pages.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------

# Neon's tooling writes both a pooled `DATABASE_URL` (pgbouncer, transaction pooling) and a
# `DATABASE_URL_UNPOOLED`. Django wants the direct one: it keeps its own connections and relies on
# session features (server-side cursors, SET TIME ZONE) that transaction pooling breaks.
_database_url = env("DATABASE_URL_UNPOOLED", default="") or env(
    "DATABASE_URL", default="postgres://galpal:galpal@localhost:5432/galpal"
)
DATABASES = {"default": env.db_url_config(_database_url)}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["ATOMIC_REQUESTS"] = False  # services own their transactions
# Ping a persistent connection before reusing it. Essential for cloud Postgres (Neon and friends
# suspend idle databases and drop connections), otherwise the first request after a pause fails.
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth / passwords -------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("full_name", "phone", "email")},
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,  # every refresh issues a new refresh token...
    "BLACKLIST_AFTER_ROTATION": True,  # ...and burns the old one
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Password reset (forgot password) one-time codes
PASSWORD_RESET_OTP_TTL_MINUTES = env.int("PASSWORD_RESET_OTP_TTL_MINUTES", default=10)
PASSWORD_RESET_OTP_MAX_ATTEMPTS = env.int("PASSWORD_RESET_OTP_MAX_ATTEMPTS", default=5)
PASSWORD_RESET_OTP_RESEND_COOLDOWN_SECONDS = env.int(
    "PASSWORD_RESET_OTP_RESEND_COOLDOWN_SECONDS", default=60
)

# --- Cache ------------------------------------------------------------------
# Redis when REDIS_URL is set (required for multi-worker production), otherwise a per-process
# in-memory cache. Failing fast on timeouts keeps a Redis outage from stalling requests.

REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "galpal",
            "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "galpal"}}

# How long the site-settings row is cached. Saving invalidates it immediately, but a per-process
# cache can't be invalidated in the *other* worker processes, so without Redis keep it short.
SITE_SETTINGS_CACHE_TTL = env.int("SITE_SETTINGS_CACHE_TTL", default=3600 if REDIS_URL else 30)

# --- Email / SMS ------------------------------------------------------------
# Email uses Django's pluggable EMAIL_BACKEND. SMS uses our own pluggable backend
# (apps.core.messaging). The full notification system arrives in Module 16.

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="GalPal <no-reply@galpal.local>")
# Safe default: messages are dropped (never logged) until a real provider is configured.
SMS_BACKEND = env("SMS_BACKEND", default="apps.core.messaging.NullSMSBackend")

# --- i18n -------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

# --- Static & media ---------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Optional S3-compatible media storage: Cloudflare R2, AWS S3, MinIO, DigitalOcean Spaces...
# Local filesystem is used unless USE_S3=True. See README "Shared cloud setup" for R2.
USE_S3 = env.bool("USE_S3", default=False)


def _token(name, default=""):
    """An env value that can never contain spaces (bucket, endpoint, region, host...), read up to
    the first whitespace so a trailing `# comment` copied from .env.example can't leak into it."""
    parts = (env(name, default=default) or "").split()
    return parts[0] if parts else ""


if USE_S3:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = _token("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = _token("AWS_S3_ENDPOINT_URL").rstrip("/") or None
    # R2 has a single pseudo-region called "auto"; a custom endpoint without a region confuses boto3.
    AWS_S3_REGION_NAME = _token("AWS_S3_REGION_NAME") or ("auto" if AWS_S3_ENDPOINT_URL else None)
    # The PUBLIC host that serves the files, e.g. pub-abc123.r2.dev or media.example.com. Host only;
    # a pasted "https://host/" is tolerated. (The R2 API endpoint above is private, so it can't be
    # used for image URLs.)
    AWS_S3_CUSTOM_DOMAIN = re.sub(r"^https?://", "", _token("AWS_S3_CUSTOM_DOMAIN")).rstrip("/") or None
    if AWS_S3_ENDPOINT_URL and "r2.cloudflarestorage.com" in AWS_S3_ENDPOINT_URL and not AWS_S3_CUSTOM_DOMAIN:
        raise ImproperlyConfigured(
            "Cloudflare R2 needs AWS_S3_CUSTOM_DOMAIN: the public host of the bucket (its r2.dev "
            "subdomain or a custom domain). Without it every image URL would point at the private "
            "API endpoint and 403."
        )
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_QUERYSTRING_AUTH = False  # media is public; return plain, cacheable URLs
    AWS_DEFAULT_ACL = None  # R2 has no ACLs and rejects the header
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}

# Upload limits (see apps.core.validators)
IMAGE_MAX_UPLOAD_SIZE = env.int("IMAGE_MAX_UPLOAD_SIZE", default=5 * 1024 * 1024)  # bytes
VIDEO_MAX_UPLOAD_SIZE = env.int("VIDEO_MAX_UPLOAD_SIZE", default=50 * 1024 * 1024)  # bytes

# --- CORS / CSRF ------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
# X-Cart-Token: the guest cart identifier (apps.cart) — sent by the client and, on its first
# response, sent back by the server, so both directions must be explicitly allowed.
CORS_ALLOW_HEADERS = [*default_headers, "x-cart-token"]
CORS_EXPOSE_HEADERS = ["x-cart-token"]
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Django REST Framework --------------------------------------------------

REST_FRAMEWORK = {
    # API only: JSON in, JSON out (plus multipart for file uploads). Swagger is the UI.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # Secure by default: public endpoints must opt in with AllowAny explicitly.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "GalPal API",
    "DESCRIPTION": (
        "REST API for the GalPal cosmetics & skincare store.\n\n"
        "Storefront endpoints live under `/api/v1/`, admin/CCE endpoints under "
        "`/api/v1/admin/`. Authenticate with `Authorization: Bearer <access token>`.\n\n"
        "All errors share one envelope: "
        "`{\"error\": {\"status\", \"code\", \"message\", \"details\"}}`."
    ),
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,  # separate request schemas (needed for file uploads)
    "SORT_OPERATIONS": False,
    # Serve Swagger UI / ReDoc assets locally instead of from a public CDN.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True, "displayRequestDuration": True},
    "ENUM_NAME_OVERRIDES": {
        "UserRoleEnum": "apps.accounts.models.User.Role",
        "StaffRoleEnum": "apps.accounts.serializers.STAFF_ROLE_CHOICES",
        "ProductStatusEnum": "apps.catalog.models.ProductStatus",
    },
    "TAGS": [
        {"name": "System", "description": "Health and operational endpoints."},
        {"name": "Auth", "description": "Register, login, JWT refresh/logout, password change and reset."},
        {"name": "Account", "description": "The logged-in user's profile and address book."},
        {"name": "Admin – Staff", "description": "Admin only: manage Admin and CCE accounts."},
        {"name": "Admin – Customers", "description": "Admin only: browse customers, activate/deactivate."},
        {"name": "Site Settings", "description": "Public, safe subset of the global site settings (branding, contact, tracking IDs, commerce flags)."},
        {"name": "Admin – Site Settings", "description": "Admin only: edit all site settings. Secrets are masked."},
        {"name": "Catalog", "description": "Public read-only categories (tree/flat), brands and tags."},
        {"name": "Admin – Categories", "description": "Admin only: category CRUD, tree, safe delete."},
        {"name": "Admin – Brands", "description": "Admin only: brand CRUD."},
        {"name": "Admin – Tags", "description": "Admin only: tag CRUD."},
        {"name": "Admin – Products", "description": "Admin only: product CRUD, variants, gallery, attributes, inventory."},
        {"name": "Hero Banners", "description": "Public: the homepage hero slider (config + active banners)."},
        {"name": "Admin – Hero Banners", "description": "Admin only: slider config and banner CRUD/reorder."},
        {"name": "Video Cards", "description": "Public: active video cards with their shoppable linked products."},
        {"name": "Admin – Video Cards", "description": "Admin only: video card CRUD."},
        {"name": "Cart", "description": "Storefront cart: guests use an X-Cart-Token header, logged-in customers use their account."},
        {"name": "Coupons", "description": "Apply or remove a coupon on the current cart."},
        {"name": "Admin – Coupons", "description": "Admin only: coupon CRUD and usage history."},
    ],
}

# --- Logging ----------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
