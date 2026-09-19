"""
Base settings shared by every environment.

Environment-specific behaviour lives in dev.py / prod.py / test.py. Secrets and
per-deployment values come from environment variables (or backend/.env).
"""

from datetime import timedelta
from pathlib import Path

import environ
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

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://galpal:galpal@localhost:5432/galpal"
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["ATOMIC_REQUESTS"] = False  # services own their transactions

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

# Optional S3-compatible media storage (AWS S3, MinIO, DigitalOcean Spaces, R2...).
# Local filesystem is used unless USE_S3=True.
USE_S3 = env.bool("USE_S3", default=False)
if USE_S3:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default=None)
    AWS_QUERYSTRING_AUTH = False  # media is public; return plain, cacheable URLs
    AWS_DEFAULT_ACL = None
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}

# Upload limits (see apps.core.validators)
IMAGE_MAX_UPLOAD_SIZE = env.int("IMAGE_MAX_UPLOAD_SIZE", default=5 * 1024 * 1024)  # bytes

# --- CORS / CSRF ------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_HEADERS = list(default_headers)
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
    },
    "TAGS": [
        {"name": "System", "description": "Health and operational endpoints."},
        {"name": "Auth", "description": "Register, login, JWT refresh/logout, password change and reset."},
        {"name": "Account", "description": "The logged-in user's profile and address book."},
        {"name": "Admin – Staff", "description": "Admin only: manage Admin and CCE accounts."},
        {"name": "Admin – Customers", "description": "Admin only: browse customers, activate/deactivate."},
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
