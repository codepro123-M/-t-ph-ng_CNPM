"""Application factory with real startup probes and one canonical API implementation."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin.bootstrap import ensure_auth_indexes, ensure_roles, ensure_super_admin
from app.auth import router as auth
from app.audio.task_manager import audio_task_manager
from app.bookings import router as bookings
from app.bookings.bootstrap import ensure_booking_indexes
from app.content.bootstrap import ensure_content_indexes
from app.content.media import UploadBodyLimitMiddleware, cleanup_loop
from app.content.router import public as public_content
from app.core.config import settings
from app.core.database import (
    assert_transaction_capability,
    close_db,
    connect_db,
    db_manager,
    refresh_transaction_readiness,
    start_transaction_readiness_loop,
)
from app.core.media_storage import media_storage
from app.core.retention import purge_expired_pii, retention_loop
from app.core.runtime_storage import verify_runtime_storage
from app.routers import (
    admin,
    ai_advisor,
    analytics,
    audio,
    content,
    localization,
    maps,
    owner,
    runtime_observability,
    ui_i18n,
)

logger = logging.getLogger("smartstay")
ROUTERS = [
    auth.router,
    content.router,
    admin.router,
    owner.router,
    bookings.router,
    audio.router,
    localization.router,
    ui_i18n.router,
    analytics.router,
    maps.router,
    ai_advisor.router,
    runtime_observability.router,
]


@asynccontextmanager
async def lifespan(app):
    tasks = []
    try:
        settings.validate_security_and_bootstrap()
        await connect_db()
        await assert_transaction_capability()
        verify_runtime_storage()
        if not await media_storage.check_backend_health(force=True):
            raise RuntimeError("Media readiness check returned false")
        await ensure_auth_indexes()
        await ensure_roles()
        await ensure_super_admin()
        await ensure_content_indexes()
        await ensure_booking_indexes()
        await audio_task_manager.ensure_indexes()
        await purge_expired_pii()
        start_transaction_readiness_loop()
        tasks = [
            asyncio.create_task(retention_loop()),
            asyncio.create_task(cleanup_loop()),
            asyncio.create_task(audio_task_manager.worker_loop()),
        ]
        app.state.started = True
        yield
    finally:
        app.state.started = False
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        await close_db()


def create_app():
    application = FastAPI(
        title="SmartStay Concierge API", version="0.5.0", lifespan=lifespan
    )
    application.add_middleware(UploadBodyLimitMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "If-None-Match",
            "X-CSRF-Token",
        ],
        expose_headers=[
            "ETag",
            "Content-Language",
            "Retry-After",
            "X-Cache",
            "X-Static-Url",
        ],
    )
    for router in ROUTERS:
        application.include_router(router)
    # URL aliases point to the same handlers and security dependencies.
    for router in (admin.router, owner.router, content.router):
        application.include_router(router, prefix="/api/v1", include_in_schema=False)
    application.include_router(
        public_content, prefix="/api/v1/content", include_in_schema=False
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        safe = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse({"detail": safe}, status_code=422)

    @application.get("/health", tags=["health"])
    async def live():
        return {"status": "alive"}

    @application.get("/health/ready", tags=["health"])
    async def ready():
        try:
            mongo = bool(await refresh_transaction_readiness())
        except Exception:
            mongo = False
        try:
            redis = db_manager.redis is not None and bool(await db_manager.redis.ping())
        except Exception:
            redis = False
        try:
            media = bool(await media_storage.check_backend_health())
        except Exception:
            media = False
        healthy = mongo and redis and media
        return JSONResponse(
            {
                "status": "ready" if healthy else "not_ready",
                "mongodb_tx_ready": mongo,
                "redis_ready": redis,
                "media_ready": media,
                "media_backend": settings.MEDIA_BACKEND.lower(),
                "mounted_routers": len(ROUTERS),
            },
            status_code=200 if healthy else 503,
        )

    return application


app = create_app()
