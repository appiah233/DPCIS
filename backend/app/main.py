import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.attempts.router import router as attempts_router
from app.auth.dependencies import AuthIdentity, require_identity
from app.config import Settings, get_settings
from app.database.session import dispose_engine, get_db
from app.exams.router import router as exams_router
from app.users.service import upsert_application_user

logger = logging.getLogger("examination_hub.api")


def _apply_security_headers(response: Response, request_id: str) -> Response:
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Examination Hub FastAPI application."""
    resolved_settings = settings or get_settings()
    is_production = resolved_settings.APP_ENV == "production"

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        dispose_engine()

    app = FastAPI(
        title=resolved_settings.APP_NAME,
        version=resolved_settings.APP_VERSION,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: resolved_settings

    @app.middleware("http")
    async def attach_request_context_and_security_headers(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error for request_id=%s path=%s",
                request_id,
                request.url.path,
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )
        return _apply_security_headers(response, request_id)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", uuid4().hex)
        if is_production:
            return JSONResponse(
                status_code=422,
                content={"detail": "Invalid request payload", "request_id": request_id},
            )
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors()), "request_id": request_id},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", uuid4().hex)
        logger.exception("Unhandled error for request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )
        return _apply_security_headers(response, request_id)

    @app.get("/", tags=["foundation"])
    def read_root() -> dict[str, str]:
        return {
            "name": resolved_settings.APP_NAME,
            "version": resolved_settings.APP_VERSION,
            "environment": resolved_settings.APP_ENV,
            "status": "ok",
        }

    @app.get("/health", tags=["foundation"])
    def read_health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/auth/me", tags=["auth"])
    def read_authenticated_identity(
        identity: AuthIdentity = Depends(require_identity),
        db=Depends(get_db),
    ) -> dict[str, str | None]:
        user = upsert_application_user(
            db,
            auth_subject=identity.subject,
            email=identity.email,
            display_name=identity.name,
        )
        return {
            "user_id": str(user.id),
            "auth_subject": user.auth_subject,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        }

    app.include_router(exams_router)
    app.include_router(attempts_router)

    return app


app = create_app()
