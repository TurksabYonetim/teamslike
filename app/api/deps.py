from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from redis.asyncio import Redis

from app.application.security.external_identity import ExternalIdentity
from app.application.security.jwt_helper import AppJWT
from app.application.services.appointment_service import AppointmentService
from app.application.services.auth_service import AuthService
from app.application.services.conversation_service import ConversationService
from app.application.services.direct_message_service import DirectMessageService
from app.application.services.external_chat_service import ExternalChatService
from app.application.services.meeting_service import MeetingService
from app.application.services.tenant_service import TenantService
from app.application.services.user_service import UserService
from app.domain.ports.cache import CachePort
from app.domain.ports.messaging_provider import MessagingProviderPort
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.ports.video_provider import VideoProviderPort
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db.session import get_sessionmaker
from app.infrastructure.db.unit_of_work import SqlUnitOfWork
from app.infrastructure.providers.chatwoot import ChatwootProvider
from app.infrastructure.providers.jitsi import JitsiProvider


@dataclass
class CurrentUser:
    user_id: UUID
    tenant_id: UUID
    email: str
    role: str


def get_uow() -> UnitOfWork:
    return SqlUnitOfWork(get_sessionmaker())


def get_jwt_helper(settings: Annotated[Settings, Depends(get_settings)]) -> AppJWT:
    return AppJWT(
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_minutes=settings.jwt_access_token_expire_minutes,
        refresh_days=settings.jwt_refresh_token_expire_days,
    )


_redis: Redis | None = None


def get_redis(settings: Annotated[Settings, Depends(get_settings)]) -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url)
    return _redis


def get_cache(
    settings: Annotated[Settings, Depends(get_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> CachePort:
    return RedisCache(redis, key_prefix=settings.redis_key_prefix)


def get_video_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VideoProviderPort:
    return JitsiProvider(
        public_url=settings.jitsi_public_url,
        app_id=settings.jitsi_jwt_app_id,
        app_secret=settings.jitsi_jwt_app_secret,
        algorithm=settings.jitsi_jwt_algorithm,
        token_ttl_minutes=settings.jitsi_jwt_token_ttl_minutes,
        domain=settings.jitsi_domain,
    )


def get_messaging_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessagingProviderPort:
    return ChatwootProvider(
        base_url=settings.chatwoot_base_url,
        user_api_token=settings.chatwoot_user_api_token,
        account_id=settings.chatwoot_account_id,
    )


def get_auth_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    jwt_helper: Annotated[AppJWT, Depends(get_jwt_helper)],
) -> AuthService:
    return AuthService(uow, jwt_helper)


def get_tenant_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> TenantService:
    return TenantService(uow)


def get_user_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> UserService:
    return UserService(uow)


def get_meeting_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    video: Annotated[VideoProviderPort, Depends(get_video_provider)],
) -> MeetingService:
    return MeetingService(uow, video)


def get_conversation_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    messaging: Annotated[MessagingProviderPort, Depends(get_messaging_provider)],
) -> ConversationService:
    return ConversationService(uow, messaging)


def get_appointment_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> AppointmentService:
    return AppointmentService(uow, meeting_service)


def get_direct_message_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> DirectMessageService:
    return DirectMessageService(uow)


def get_external_chat_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    messaging: Annotated[MessagingProviderPort, Depends(get_messaging_provider)],
) -> ExternalChatService:
    return ExternalChatService(uow, messaging)


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    jwt_helper: AppJWT = Depends(get_jwt_helper),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = jwt_helper.decode(token)
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    return CurrentUser(
        user_id=UUID(payload["sub"]),
        tenant_id=UUID(payload["tid"]),
        email=payload.get("email", ""),
        role=payload.get("role", "member"),
    )


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role not in ("owner", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


async def get_external_identity(
    authorization: Annotated[str | None, Header()] = None,
    uow: UnitOfWork = Depends(get_uow),
) -> ExternalIdentity:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        unverified = jwt.get_unverified_claims(token)
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    iss = unverified.get("iss")
    if not iss:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing 'iss' (tenant slug)")
    async with uow as u:
        tenant = await u.tenants.get_by_slug(str(iss))
    if not tenant or not tenant.signing_secret:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Unknown tenant or tenant has no signing secret",
        )
    try:
        payload = jwt.decode(token, tenant.signing_secret, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, f"Token verification failed: {e}"
        ) from e
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing 'sub'")
    return ExternalIdentity(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        external_sub=str(sub),
        email=str(payload.get("email", "")),
        name=str(payload.get("name", "")),
    )
