"""
Settings are evaluated at import time, so these run in a fresh interpreter with a controlled
environment. What they protect: a mistyped R2 config fails loudly at startup instead of serving
broken image URLs, and — most importantly — the test suite can never touch a shared cloud database
or bucket, even when a developer's .env points at them.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]

PROBE = """
import json
from django.conf import settings
print(json.dumps({
  "storage": settings.STORAGES["default"]["BACKEND"],
  "db": {k: settings.DATABASES["default"].get(k) for k in ("NAME", "HOST", "USER")},
  "options": settings.DATABASES["default"].get("OPTIONS"),
  "custom_domain": getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None),
  "region": getattr(settings, "AWS_S3_REGION_NAME", None),
  "sig": getattr(settings, "AWS_S3_SIGNATURE_VERSION", None),
  "acl": getattr(settings, "AWS_DEFAULT_ACL", "unset"),
  "querystring_auth": getattr(settings, "AWS_QUERYSTRING_AUTH", "unset"),
  "health_checks": settings.DATABASES["default"].get("CONN_HEALTH_CHECKS"),
}))
"""

R2_ENV = {
    "USE_S3": "True",
    "AWS_ACCESS_KEY_ID": "key",
    "AWS_SECRET_ACCESS_KEY": "secret",
    "AWS_STORAGE_BUCKET_NAME": "galpal-media",
    "AWS_S3_ENDPOINT_URL": "https://abc123.r2.cloudflarestorage.com",
}


# Settings also read backend/.env, which on a developer's machine may hold real cloud values. Real
# environment variables win over .env, so pin EVERY variable these tests care about; otherwise a
# test that relies on "not set" would silently pick up whatever the developer's .env says.
BASELINE = {
    "USE_S3": "False",
    "AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": "", "AWS_STORAGE_BUCKET_NAME": "",
    "AWS_S3_ENDPOINT_URL": "", "AWS_S3_REGION_NAME": "", "AWS_S3_CUSTOM_DOMAIN": "",
    "DATABASE_URL": "postgres://galpal:galpal@localhost:5432/galpal",
    "DATABASE_URL_UNPOOLED": "",
    "TEST_DATABASE_URL": "postgres://galpal:galpal@localhost:5432/galpal",
}


def load_settings(module, **env):
    """Import `module` in a clean interpreter; returns (returncode, parsed json or None, stderr)."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("AWS_", "USE_S3", "DATABASE_URL", "TEST_DATABASE_URL"))}
    clean.update({"DJANGO_SETTINGS_MODULE": module, "SECRET_KEY": "x", **BASELINE, **env})
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=BACKEND, env=clean, capture_output=True, text=True)
    data = json.loads(result.stdout.strip().splitlines()[-1]) if result.returncode == 0 and result.stdout.strip() else None
    return result.returncode, data, result.stderr


def test_default_is_local_filesystem_storage():
    code, data, err = load_settings("config.settings.dev")
    assert code == 0, err
    assert data["storage"] == "django.core.files.storage.FileSystemStorage"


def test_r2_without_a_public_domain_fails_at_startup():
    code, _, err = load_settings("config.settings.dev", **R2_ENV)
    assert code != 0 and "AWS_S3_CUSTOM_DOMAIN" in err


def test_r2_config_is_normalised():
    env = {**R2_ENV, "AWS_S3_ENDPOINT_URL": R2_ENV["AWS_S3_ENDPOINT_URL"] + "/"}  # trailing slash tolerated too
    code, data, err = load_settings("config.settings.dev", **env, AWS_S3_CUSTOM_DOMAIN="https://pub-abc123.r2.dev/")
    assert code == 0, err
    assert data["storage"] == "storages.backends.s3.S3Storage"
    assert data["custom_domain"] == "pub-abc123.r2.dev"  # scheme and trailing slash stripped
    assert data["region"] == "auto" and data["sig"] == "s3v4"
    assert data["acl"] is None and data["querystring_auth"] is False


def test_an_explicit_region_is_respected():
    code, data, err = load_settings("config.settings.dev", **R2_ENV, AWS_S3_CUSTOM_DOMAIN="cdn.example.com", AWS_S3_REGION_NAME="weur")
    assert code == 0, err
    assert data["region"] == "weur"


def test_a_non_r2_endpoint_does_not_require_a_custom_domain():
    env = {**R2_ENV, "AWS_S3_ENDPOINT_URL": "http://localhost:9000"}  # e.g. MinIO
    code, data, err = load_settings("config.settings.dev", **env)
    assert code == 0, err
    assert data["custom_domain"] is None


def test_database_gets_connection_health_checks():
    code, data, err = load_settings("config.settings.dev", DATABASE_URL="postgres://u:p@db.example.com:5432/shared?sslmode=require")
    assert code == 0, err
    assert data["health_checks"] is True
    assert data["options"] == {"sslmode": "require"}  # a cloud Postgres connection string just works


# --- the test suite must never touch shared cloud resources --------------------------------------


def test_tests_ignore_a_cloud_storage_config_in_the_environment():
    code, data, err = load_settings("config.settings.test", **R2_ENV, AWS_S3_CUSTOM_DOMAIN="pub-abc123.r2.dev")
    assert code == 0, err
    assert data["storage"] == "django.core.files.storage.FileSystemStorage"


def test_tests_ignore_a_shared_cloud_database_url():
    code, data, err = load_settings(
        "config.settings.test", DATABASE_URL="postgres://team:secret@ep-x.neon.tech:5432/shared?sslmode=require"
    )
    assert code == 0, err
    assert data["db"]["HOST"] == "localhost" and data["db"]["NAME"] == "galpal"
    assert "neon" not in json.dumps(data)
    assert not data["options"]  # no sslmode leaking onto the local connection


def test_tests_database_can_be_overridden_explicitly():
    code, data, err = load_settings("config.settings.test", TEST_DATABASE_URL="postgres://me:pw@localhost:5433/mytests")
    assert code == 0, err
    assert data["db"]["NAME"] == "mytests" and data["db"]["USER"] == "me"


# --- robustness against a hand-edited .env -------------------------------------------------------


def test_trailing_comments_copied_into_env_values_do_not_corrupt_them():
    """Regression: `AWS_S3_REGION_NAME=auto   # optional...` used to become the whole string."""
    env = {
        **R2_ENV,
        "AWS_S3_REGION_NAME": "auto       # optional: defaults to auto",
        "AWS_S3_CUSTOM_DOMAIN": "https://pub-abc123.r2.dev/   # PUBLIC host of the bucket",
        "AWS_STORAGE_BUCKET_NAME": "galpal-media  # the bucket",
    }
    code, data, err = load_settings("config.settings.dev", **env)
    assert code == 0, err
    assert data["region"] == "auto" and data["custom_domain"] == "pub-abc123.r2.dev"


def test_the_direct_neon_url_wins_over_the_pooled_one():
    pooled = "postgres://u:p@ep-x-pooler.ap-southeast-1.aws.neon.tech/db?sslmode=require"
    direct = "postgres://u:p@ep-x.ap-southeast-1.aws.neon.tech/db?sslmode=require"
    code, data, err = load_settings("config.settings.dev", DATABASE_URL=pooled, DATABASE_URL_UNPOOLED=direct)
    assert code == 0, err
    assert data["db"]["HOST"] == "ep-x.ap-southeast-1.aws.neon.tech"


def test_the_pooled_url_is_used_when_there_is_no_direct_one():
    code, data, err = load_settings("config.settings.dev", DATABASE_URL="postgres://u:p@some-host:5432/db")
    assert code == 0, err
    assert data["db"]["HOST"] == "some-host"
