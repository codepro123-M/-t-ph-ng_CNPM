import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.database import (
    connect_db,
    assert_transaction_capability,
    refresh_transaction_readiness,
    start_transaction_readiness_loop,
    close_db,
    db_manager,
)
from app.core.media_storage import MediaStorageError, media_storage
from app.core.runtime_storage import ensure_runtime_storage, verify_runtime_storage

from app.content.router import router as content_router
from app.content.router import public as public_content_router
from app.audio.router import router as audio_router
from app.admin.router import router as admin_router
from app.owner.router import router as owner_router
from app.ai_advisor.router import router as ai_advisor_router
from app.analytics.router import router as analytics_router
from app.localization.router import router as localization_router
from app.maps.router import router as maps_router
from app.runtime_observability.router import router as runtime_observability_router
from app.ui_i18n.router import router as ui_i18n_router
from app.auth.router import router as auth_router, ensure_auth_indexes
from app.admin.bootstrap import ensure_roles, ensure_super_admin
from app.core.retention import purge_expired_pii, retention_loop, stop_retention
from app.content.bootstrap import ensure_content_indexes
from app.content.media import UploadBodyLimitMiddleware, cleanup_loop
from app.bookings.router import router as bookings_router
from app.bookings.bootstrap import ensure_booking_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("smartstay.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Starting Smart Stay & Audio Concierge Backend ===")

    # Tier 1: Security + Bootstrap Guard
    settings.validate_security_and_bootstrap()
    logger.info("[Tier 1] Security secrets & bootstrap mode validated.")

    retention_task = None
    cleanup_task = None
    try:
        # Tier 2: Database / Cache / Media Readiness
        await connect_db()
        await assert_transaction_capability()
        await ensure_auth_indexes()
        media_ok = await media_storage.check_backend_health(force=True)
        if not media_ok:
            raise RuntimeError("Media storage readiness check returned false.")
        logger.info("[Tier 2] MongoDB, Redis, media & auth indexes ready.")

        # Tier 3: Runtime Storage Prep
        if settings.APP_ENV.lower() in {"dev", "development"}:
            ensure_runtime_storage()
        else:
            verify_runtime_storage()
        logger.info("[Tier 3] Runtime storage directories prepared.")

        await ensure_roles()
        await ensure_super_admin()
        await ensure_content_indexes()
        await ensure_booking_indexes()
        await purge_expired_pii()
        retention_task = asyncio.create_task(retention_loop())
        cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("[Phase 2] RBAC, bootstrap and PII retention ready.")

        # Tier 4: Recovery + Background Workers
        await refresh_transaction_readiness()
        start_transaction_readiness_loop()
        logger.info("[Tier 4] Transaction readiness loop started.")

        yield
    finally:
        logger.info("=== Shutting down Smart Stay Backend ===")
        await stop_retention(retention_task)
        await stop_retention(cleanup_task)
        await close_db()


def create_app() -> FastAPI:
    ensure_runtime_storage()

    app = FastAPI(
        title="Hệ Thống Quản Lý Homestay/Khách Sạn & Thuyết Minh Đa Ngôn Ngữ",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
    app.add_middleware(UploadBodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "If-None-Match",
        ],
        expose_headers=["ETag", "Content-Language"],
    )

    @app.exception_handler(RequestValidationError)
    async def safe_validation_error(request, exc):
        # Never echo password, national ID, token, or an entire invalid request.
        errors = [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(PyMongoError)
    async def safe_database_error(request, exc):
        if exc.has_error_label("TransientTransactionError"):
            return JSONResponse(
                status_code=409,
                content={"detail": "Concurrent update; reload and retry"},
            )
        logger.error("Database operation failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503, content={"detail": "Database operation unavailable"}
        )

    routers = (
        bookings_router,
        auth_router,
        content_router,
        audio_router,
        admin_router,
        owner_router,
        ai_advisor_router,
        analytics_router,
        localization_router,
        maps_router,
        runtime_observability_router,
        ui_i18n_router,
    )
    for router in routers:
        app.include_router(router)
    # Preserve old /api/v1 URLs while exposing the Phase 2 contract in Swagger.
    app.include_router(admin_router, prefix="/api/v1", include_in_schema=False)
    app.include_router(owner_router, prefix="/api/v1", include_in_schema=False)
    app.include_router(content_router, prefix="/api/v1", include_in_schema=False)
    app.include_router(
        public_content_router, prefix="/api/v1/content", include_in_schema=False
    )

    @app.get("/health", tags=["system"])
    async def health_check():
        return {"status": "alive", "service": "smart-stay-backend"}

    @app.get("/health/ready", tags=["system"])
    async def readiness_check():
        try:
            await db_manager.client.admin.command("ping")
            redis_ok = await db_manager.redis.ping()
            tx_ready = await refresh_transaction_readiness()
            media_ok = await media_storage.check_backend_health()
            if not (redis_ok and tx_ready and media_ok):
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "status": "not_ready",
                        "mongodb_tx_ready": tx_ready,
                        "redis_ready": bool(redis_ok),
                        "media_backend": settings.MEDIA_BACKEND.strip().lower(),
                        "media_ready": bool(media_ok),
                    },
                )
            return {
                "status": "ready",
                "mongodb_tx_ready": tx_ready,
                "redis_ready": True,
                "media_backend": settings.MEDIA_BACKEND.strip().lower(),
                "media_ready": True,
                "mounted_routers": len(routers),
            }
        except MediaStorageError as exc:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "media_backend": settings.MEDIA_BACKEND.strip().lower(),
                    "media_ready": False,
                    "error": str(exc),
                },
            )
        except Exception as exc:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "error": str(exc)},
            )

    return app


app = create_app()
