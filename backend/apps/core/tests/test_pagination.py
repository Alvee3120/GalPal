import pytest

from apps.core.pagination import StandardPagination

pytestmark = pytest.mark.urls("apps.core.tests.urls")


def test_defaults():
    assert StandardPagination.page_size == 20
    assert StandardPagination.max_page_size == 100


def test_default_page_size_and_shape(api_client):
    body = api_client.get("/numbers/").json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 250
    assert len(body["results"]) == 20
    assert body["previous"] is None
    assert body["next"].endswith("?page=2")


def test_second_page_links_both_ways(api_client):
    body = api_client.get("/numbers/?page=2").json()
    assert body["results"][0] == 20
    assert body["previous"] is not None and body["next"] is not None


def test_page_size_param_is_honoured(api_client):
    assert len(api_client.get("/numbers/?page_size=5").json()["results"]) == 5


def test_page_size_is_capped_at_100(api_client):
    assert len(api_client.get("/numbers/?page_size=1000").json()["results"]) == 100


def test_invalid_page_uses_error_envelope(api_client):
    response = api_client.get("/numbers/?page=999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
