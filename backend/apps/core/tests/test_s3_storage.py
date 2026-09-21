"""
The real S3/R2 code path (boto3 + django-storages) against `moto`, an in-process fake S3: upload,
public URL, replace, delete and copy all go through the same calls Cloudflare R2 would receive,
without needing an account. (R2 is S3-compatible; the R2-specific bits — endpoint, "auto" region,
public domain — are settings, covered in test_storage_settings.py.)
"""
import io

import boto3
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from moto import mock_aws
from PIL import Image

pytestmark = pytest.mark.django_db

BUCKET = "galpal-media"
PUBLIC_HOST = "media.example.test"


@pytest.fixture
def bucket(settings):
    # Guard: an inherited endpoint (e.g. a developer's real R2 URL) would bypass moto entirely.
    assert not getattr(settings, "AWS_S3_ENDPOINT_URL", None), "tests must never see a real S3 endpoint"
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        settings.STORAGES = {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": {
                    "access_key": "test", "secret_key": "test", "bucket_name": BUCKET, "region_name": "us-east-1",
                    "endpoint_url": None, "custom_domain": PUBLIC_HOST, "querystring_auth": False, "default_acl": None,
                    "signature_version": "s3v4",
                },
            },
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        yield client


def keys(client):
    return {obj["Key"] for obj in client.list_objects_v2(Bucket=BUCKET).get("Contents", [])}


def png(name="a.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "pink").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue())


# --- the storage itself ------------------------------------------------------------------------


def test_this_really_is_the_s3_backend(bucket):
    assert default_storage.__class__.__name__ == "S3Storage"  # `default_storage` is a lazy proxy; this resolves it


def test_save_url_exists_delete(bucket):
    name = default_storage.save("products/2026/09/x.png", ContentFile(b"data"))
    assert name in keys(bucket) and default_storage.exists(name)
    url = default_storage.url(name)
    assert url == f"https://{PUBLIC_HOST}/{name}"  # public host, no signature query string
    default_storage.delete(name)
    assert name not in keys(bucket) and not default_storage.exists(name)


# --- through the API: this is what the team's admin panel actually does ---------------------------


def test_uploading_a_category_image_stores_it_in_the_bucket_and_returns_a_public_url(bucket, auth_client, admin_user):
    r = auth_client(admin_user).post("/api/v1/admin/categories/", {"name": "Skincare", "image": png()}, format="multipart")
    assert r.status_code == 201
    url = r.json()["image"]
    assert url.startswith(f"https://{PUBLIC_HOST}/categories/") and "?" not in url  # not a signed URL
    assert url.removeprefix(f"https://{PUBLIC_HOST}/") in keys(bucket)


def test_replacing_and_deleting_remove_the_old_objects(bucket, auth_client, admin_user, django_capture_on_commit_callbacks):
    client = auth_client(admin_user)
    with django_capture_on_commit_callbacks(execute=True):
        created = client.post("/api/v1/admin/categories/", {"name": "Hair", "image": png("one.png")}, format="multipart").json()
    (first,) = keys(bucket)
    with django_capture_on_commit_callbacks(execute=True):
        client.patch(f"/api/v1/admin/categories/{created['id']}/", {"image": png("two.png")}, format="multipart")
    (second,) = keys(bucket)
    assert second != first  # the old object was removed, the new one stored
    with django_capture_on_commit_callbacks(execute=True):
        assert client.delete(f"/api/v1/admin/categories/{created['id']}/").status_code == 204
    assert keys(bucket) == set()


def test_product_duplicate_copies_images_between_objects(bucket):
    """`duplicate_product` re-reads each image from storage: it must work against remote files."""
    from apps.catalog import services
    from apps.catalog.tests.factories import ProductFactory

    original = ProductFactory()
    copy = services.duplicate_product(original)
    assert original.feature_image.name != copy.feature_image.name
    assert {original.feature_image.name, copy.feature_image.name} <= keys(bucket)


def test_product_image_urls_in_the_public_api_are_the_public_host(bucket, api_client):
    from apps.catalog.tests.factories import ProductFactory

    product = ProductFactory()
    body = api_client.get(f"/api/v1/products/{product.slug}/").json()
    assert body["feature_image"].startswith(f"https://{PUBLIC_HOST}/products/")


def test_uploading_a_video_and_thumbnail(bucket, auth_client, admin_user):
    video = SimpleUploadedFile("clip.mp4", b"\x00\x00\x00\x18ftypmp42" + b"0" * 64, content_type="video/mp4")
    r = auth_client(admin_user).post(
        "/api/v1/admin/videos/", {"title": "Demo", "video_file": video, "thumbnail": png()}, format="multipart"
    )
    assert r.status_code == 201, r.json()
    assert r.json()["video_url"].startswith(f"https://{PUBLIC_HOST}/videos/")
    assert len(keys(bucket)) == 2
