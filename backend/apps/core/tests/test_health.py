from unittest import mock

import pytest
from django.db import OperationalError


@pytest.mark.django_db
def test_health_ok_without_authentication(api_client):
    response = api_client.get("/api/v1/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok"}
    assert body["service"] == "GalPal API"
    assert body["version"]
    assert body["time"]


def test_health_ignores_bad_credentials(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    with mock.patch("apps.core.views.check_database", return_value="ok"):
        assert api_client.get("/api/v1/health/").status_code == 200


def test_health_reports_503_when_database_is_down(api_client):
    broken = mock.MagicMock()
    broken.cursor.side_effect = OperationalError("connection refused")
    with mock.patch("apps.core.views.connection", broken):
        response = api_client.get("/api/v1/health/")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"] == {"database": "error"}
    assert "connection refused" not in response.content.decode()


def test_health_only_allows_get(api_client):
    assert api_client.post("/api/v1/health/").status_code == 405
