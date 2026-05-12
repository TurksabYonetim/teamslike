from fastapi import Request
from fastapi.responses import JSONResponse

from app.application.security.jwt_helper import JWTError_
from app.domain.exceptions import (
    AlreadyExistsError,
    AppointmentConflictError,
    DomainError,
    InvalidCredentialsError,
    NotFoundError,
    ProviderError,
    TenantInactiveError,
)


def register_exception_handlers(app):
    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AlreadyExistsError)
    async def _conflict(request: Request, exc: AlreadyExistsError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidCredentialsError)
    async def _unauth(request: Request, exc: InvalidCredentialsError):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(TenantInactiveError)
    async def _tenant_inactive(request: Request, exc: TenantInactiveError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(AppointmentConflictError)
    async def _appt_conflict(request: Request, exc: AppointmentConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def _provider(request: Request, exc: ProviderError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(JWTError_)
    async def _jwt(request: Request, exc: JWTError_):
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    @app.exception_handler(DomainError)
    async def _generic_domain(request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
