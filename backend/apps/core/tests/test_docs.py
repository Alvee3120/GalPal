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
