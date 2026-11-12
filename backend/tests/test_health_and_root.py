from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_root_returns_basic_application_info(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "name": "Examination Hub API",
        "version": "0.1.0",
        "environment": "test",
        "status": "ok",
    }


def test_health_returns_http_200_and_expected_minimal_document(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_exposes_no_secrets_env_or_infra_details(client: TestClient) -> None:
    response = client.get("/health")
    body_text = response.text.lower()

    assert list(response.json().keys()) == ["status"]
    for forbidden_term in (
        "database",
        "postgres",
        "neon",
        "auth",
        "secret",
        "aws",
        "traceback",
        "env",
    ):
        assert forbidden_term not in body_text


def test_security_and_request_id_headers_are_applied(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req-foundation-123"})

    assert response.headers["X-Request-ID"] == "req-foundation-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Cache-Control"] == "no-store"


def test_unhandled_exception_does_not_leak_stack_trace() -> None:
    settings = Settings(_env_file=None, APP_ENV="test")
    app = create_app(settings=settings)
    boom_router = APIRouter()

    @boom_router.get("/__test_boom")
    def trigger_boom() -> dict[str, str]:
        raise RuntimeError("sensitive internal detail: db=secret")

    @boom_router.get("/__test_http_error")
    def trigger_http_error() -> dict[str, str]:
        raise HTTPException(status_code=404, detail="Item not found")

    app.include_router(boom_router)

    with TestClient(app, raise_server_exceptions=False) as client:
        boom_response = client.get("/__test_boom")
        assert boom_response.status_code == 500
        boom_payload = boom_response.json()
        assert boom_payload["detail"] == "Internal server error"
        assert "request_id" in boom_payload
        assert "sensitive internal detail" not in boom_response.text
        assert "traceback" not in boom_response.text.lower()

        http_err_response = client.get("/__test_http_error")
        assert http_err_response.status_code == 404
        assert http_err_response.json() == {"detail": "Item not found"}


def test_production_app_disables_openapi_and_docs_endpoints() -> None:
    prod_settings = Settings(
        _env_file=None,
        APP_ENV="production",
        CORS_ORIGINS=["https://exams.example.com"],
        DATABASE_URL="postgresql://user:pass@ep-demo.us-east-1.aws.neon.tech/neondb?sslmode=require",
        NEON_AUTH_JWKS_URL="https://auth.example.com/.well-known/jwks.json",
        NEON_AUTH_BASE_URL="https://auth.example.com",
    )
    app = create_app(settings=prod_settings)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
