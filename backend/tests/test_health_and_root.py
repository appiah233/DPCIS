import pytest
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.database.session import get_db
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


def test_health_accepts_vercel_api_service_prefix(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_vercel_api_prefix_normalization_preserves_api_routers(client: TestClient) -> None:
    root_api = client.get("/api")
    root_api_slash = client.get("/api/")
    auth_me_direct = client.get("/auth/me")
    auth_me_prefixed = client.get("/api/auth/me")
    admin_direct = client.get("/api/admin/exams")
    admin_gateway = client.get("/api/api/admin/exams")
    admin_over_stripped = client.get("/api/api/api/admin/exams")

    assert root_api.status_code == 200
    assert root_api.json()["status"] == "ok"
    assert root_api_slash.status_code == 200
    assert root_api_slash.json()["status"] == "ok"

    # Unauthenticated calls reach the auth guard cleanly (401, never 404).
    assert auth_me_direct.status_code == 401
    assert auth_me_prefixed.status_code == 401
    assert admin_direct.status_code == 401
    assert admin_gateway.status_code == 401

    # Do not strip /api recursively.
    assert admin_over_stripped.status_code == 404


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
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/redoc").status_code == 404
        assert client.get("/api/openapi.json").status_code == 404


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_default_local_cors_allows_localhost_and_127_0_0_1_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
    origin: str,
) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    dev_settings = Settings(_env_file=None, APP_ENV="development")
    app = create_app(settings=dev_settings)

    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-origin") != "*"
    assert response.headers.get("access-control-allow-credentials") != "true"
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_default_local_cors_preflight_and_401_include_headers_for_local_origins(
    monkeypatch: pytest.MonkeyPatch,
    origin: str,
) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    dev_settings = Settings(_env_file=None, APP_ENV="development")
    app = create_app(settings=dev_settings)
    app.dependency_overrides[get_db] = lambda: None

    with TestClient(app) as client:
        preflight = client.options(
            "/auth/me",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        unauth_get = client.get("/auth/me", headers={"Origin": origin})

    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == origin
    assert preflight.headers.get("access-control-allow-credentials") != "true"
    assert "access-control-allow-credentials" not in preflight.headers
    allowed_headers = preflight.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers

    assert unauth_get.status_code == 401
    assert unauth_get.headers.get("access-control-allow-origin") == origin
    assert unauth_get.headers.get("access-control-allow-credentials") != "true"
    assert "access-control-allow-credentials" not in unauth_get.headers


def test_cors_rejects_disallowed_third_party_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    dev_settings = Settings(_env_file=None, APP_ENV="development")
    app = create_app(settings=dev_settings)

    with TestClient(app) as client:
        get_resp = client.get("/health", headers={"Origin": "https://evil.example.com"})
        options_resp = client.options(
            "/auth/me",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert get_resp.status_code == 200
    assert "access-control-allow-origin" not in get_resp.headers
    assert "access-control-allow-credentials" not in get_resp.headers

    assert options_resp.status_code == 400
    assert "access-control-allow-origin" not in options_resp.headers
    assert "access-control-allow-credentials" not in options_resp.headers
