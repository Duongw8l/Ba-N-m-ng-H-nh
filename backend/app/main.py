from fastapi import FastAPI

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
    app.include_router(health_router, prefix=API_PREFIX)
    return app


app = create_app()
