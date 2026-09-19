import pytest

pytestmark = pytest.mark.urls("apps.core.tests.urls")


def assert_envelope(response, status, code):
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"status", "code", "message", "details"}
    assert body["error"]["status"] == status == response.status_code
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    return body["error"]


def test_serializer_validation_error_lists_field_errors(api_client):
    response = api_client.post("/validation/", {"qty": 0}, format="json")
    error = assert_envelope(response, 400, "validation_error")
    assert error["message"] == "Validation failed."
    assert set(error["details"]) == {"phone", "qty"}
    assert error["details"]["phone"] == ["This field is required."]


def test_non_field_validation_error_details_is_a_dict(api_client):
    error = assert_envelope(api_client.get("/list-validation/"), 400, "validation_error")
    assert error["details"] == {"non_field_errors": ["Something is wrong overall."]}


def test_django_validation_error_is_converted(api_client):
    error = assert_envelope(api_client.get("/django-validation/"), 400, "validation_error")
    assert error["details"] == {"sku": ["Duplicate SKU."]}


def test_unauthenticated_is_401_with_challenge_header(api_client):
    response = api_client.get("/protected/")
    assert_envelope(response, 401, "not_authenticated")
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_invalid_token_is_401_envelope(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    error = assert_envelope(api_client.get("/protected/"), 401, "token_not_valid")
    assert error["details"] is None


def test_permission_denied_is_403(api_client):
    error = assert_envelope(api_client.get("/forbidden/"), 403, "permission_denied")
    assert error["message"] == "Admins only."


def test_django_permission_denied_is_403(api_client):
    assert_envelope(api_client.get("/django-forbidden/"), 403, "permission_denied")


def test_django_http404_is_404(api_client):
    assert_envelope(api_client.get("/django-404/"), 404, "not_found")


def test_method_not_allowed_is_405(api_client):
    assert_envelope(api_client.delete("/forbidden/"), 405, "method_not_allowed")


def test_throttled_reports_retry_after(api_client):
    error = assert_envelope(api_client.get("/throttled/"), 429, "throttled")
    assert error["details"] == {"retry_after": 30}


def test_unhandled_exception_is_500_and_hides_internals(api_client):
    api_client.raise_request_exception = False
    response = api_client.get("/boom/")
    error = assert_envelope(response, 500, "server_error")
    assert "secret internal detail" not in response.content.decode()
    assert error["message"] == "A server error occurred."


def test_unknown_url_returns_json_404(client):
    response = client.get("/definitely/not/a/route/")
    assert_envelope(response, 404, "not_found")
    assert response["Content-Type"] == "application/json"
