from fastapi import FastAPI

from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.classes.router import router as classes_router
from app.core.authorize import AuthorizationError, authorization_error_handler
from app.core.config import get_settings
from app.core.health import router as health_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    # Swagger chỉ bật khi phát triển: tài liệu API không nên công khai ở môi trường thật.
    docs_enabled = settings.app_env != "production"
    app = FastAPI(
        title="Trợ lý AI quản lý lớp học THPT",
        version="0.1.0",
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )
    # authorize() ném AuthorizationError ở bất kỳ đâu (endpoint, về sau cả tool của LLM); ở HTTP
    # nó luôn thành 403 với thông điệp chung.
    app.add_exception_handler(AuthorizationError, authorization_error_handler)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(classes_router, prefix=API_PREFIX)
    app.include_router(analytics_router, prefix=API_PREFIX)
    return app


app = create_app()
