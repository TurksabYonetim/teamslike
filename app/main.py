from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.deps import get_redis
from app.api.exceptions import register_exception_handlers
from app.api.v1 import (
    appointments,
    auth,
    conversations,
    direct_messages,
    inbox,
    meetings,
    portal_me,
    tenants,
    users,
)
from app.infrastructure.config import get_settings
from app.infrastructure.db.session import get_engine
from app.infrastructure.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def _init_sentry(settings) -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    _init_sentry(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    register_exception_handlers(app)

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    @app.get("/ready", tags=["meta"])
    async def ready(redis: Redis = Depends(get_redis)):
        checks: dict[str, str] = {}
        status_code = 200

        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {type(exc).__name__}"
            status_code = 503

        try:
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {type(exc).__name__}"
            status_code = 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if status_code == 200 else "not_ready",
                "checks": checks,
            },
        )

    api_v1_prefix = "/v1"
    app.include_router(auth.router, prefix=api_v1_prefix)
    app.include_router(tenants.router, prefix=api_v1_prefix)
    app.include_router(users.router, prefix=api_v1_prefix)
    app.include_router(meetings.router, prefix=api_v1_prefix)
    app.include_router(conversations.router, prefix=api_v1_prefix)
    app.include_router(appointments.router, prefix=api_v1_prefix)
    app.include_router(direct_messages.router, prefix=api_v1_prefix)
    app.include_router(portal_me.router, prefix=api_v1_prefix)
    app.include_router(inbox.router, prefix=api_v1_prefix)

    return app


app = create_app()
