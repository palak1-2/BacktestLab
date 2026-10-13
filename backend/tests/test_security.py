from fastapi.testclient import TestClient

from app.main import app


def test_untrusted_origin_receives_no_cors_permission():
    with TestClient(app) as client:
        response = client.get(
            "/openapi.json",
            headers={"Origin": "https://untrusted.example"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_is_not_permitted():
    with TestClient(app) as client:
        response = client.options(
            "/openapi.json",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert "access-control-allow-origin" not in response.headers
