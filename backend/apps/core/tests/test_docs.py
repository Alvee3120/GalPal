import yaml


def test_swagger_ui_is_served(client):
    response = client.get("/api/docs/")
    assert response.status_code == 200
    assert b"swagger" in response.content.lower()


def test_redoc_is_served(client):
    assert client.get("/api/redoc/").status_code == 200


def test_schema_documents_health_endpoint(client):
    response = client.get("/api/schema/")
    assert response.status_code == 200
    schema = yaml.safe_load(response.content)
    assert schema["info"]["title"] == "GalPal API"
    operation = schema["paths"]["/api/v1/health/"]["get"]
    assert operation["tags"] == ["System"]
    assert {"200", "503"} <= set(operation["responses"])


def test_schema_documents_auth_and_admin_endpoints(client):
    schema = yaml.safe_load(client.get("/api/schema/").content)
    paths = schema["paths"]
    for path in [
        "/api/v1/auth/register/", "/api/v1/auth/login/", "/api/v1/auth/token/refresh/", "/api/v1/auth/logout/",
        "/api/v1/auth/password/change/", "/api/v1/auth/password/forgot/", "/api/v1/auth/password/reset/",
        "/api/v1/account/profile/", "/api/v1/account/addresses/", "/api/v1/account/addresses/{id}/set-default/",
        "/api/v1/admin/staff/", "/api/v1/admin/staff/{id}/deactivate/",
        "/api/v1/admin/customers/", "/api/v1/admin/customers/{id}/",
        "/api/v1/site-settings/", "/api/v1/admin/site-settings/",
        "/api/v1/categories/", "/api/v1/categories/tree/", "/api/v1/categories/{slug}/",
        "/api/v1/brands/", "/api/v1/brands/{slug}/", "/api/v1/tags/", "/api/v1/tags/{slug}/",
        "/api/v1/admin/categories/", "/api/v1/admin/categories/{id}/", "/api/v1/admin/categories/tree/",
        "/api/v1/admin/brands/", "/api/v1/admin/brands/{id}/", "/api/v1/admin/tags/", "/api/v1/admin/tags/{id}/",
    ]:
        assert path in paths, path
    # every operation is tagged, so Swagger groups them
    assert all(op.get("tags") for item in paths.values() for m, op in item.items() if m in {"get", "post", "patch", "delete"})


def test_schema_declares_bearer_auth_only_on_protected_endpoints(client):
    schema = yaml.safe_load(client.get("/api/schema/").content)
    schemes = schema["components"]["securitySchemes"]
    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemes.values())
    paths = schema["paths"]
    assert paths["/api/v1/account/profile/"]["get"]["security"] == [{"jwtAuth": []}]
    assert paths["/api/v1/admin/staff/"]["get"]["security"] == [{"jwtAuth": []}]
    for public in ["/api/v1/auth/login/", "/api/v1/auth/register/", "/api/v1/auth/password/forgot/"]:
        assert paths[public]["post"]["security"] == [{}], public  # no padlock in Swagger


def test_schema_role_enums_have_readable_names(client):
    schema = yaml.safe_load(client.get("/api/schema/").content)
    enums = set(schema["components"]["schemas"])
    assert {"UserRoleEnum", "StaffRoleEnum"} <= enums
    assert not any(name.startswith("Role") and name.endswith("Enum") for name in enums)
