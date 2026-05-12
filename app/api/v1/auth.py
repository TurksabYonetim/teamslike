from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_auth_service, get_current_user
from app.api.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterUserRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from app.application.dto.auth import LoginCommand, RegisterUserCommand, SignupCommand
from app.application.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=SignupResponse)
async def signup(
    body: SignupRequest, svc: Annotated[AuthService, Depends(get_auth_service)]
) -> SignupResponse:
    tenant, user, tokens = await svc.signup(
        SignupCommand(
            tenant_slug=body.tenant_slug.lower(),
            tenant_name=body.tenant_name,
            admin_email=body.admin_email,
            admin_full_name=body.admin_full_name,
            admin_password=body.admin_password,
        )
    )
    return SignupResponse(
        tenant={"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name},
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
        },
        tokens=TokenResponse(
            access_token=tokens.access_token, refresh_token=tokens.refresh_token
        ),
    )


@router.post("/register-user", status_code=status.HTTP_201_CREATED, response_model=SignupResponse)
async def register_user(
    body: RegisterUserRequest, svc: Annotated[AuthService, Depends(get_auth_service)]
) -> SignupResponse:
    tenant, user, tokens = await svc.register_user(
        RegisterUserCommand(
            tenant_id=body.tenant_id,
            email=body.email,
            full_name=body.full_name,
            password=body.password,
        )
    )
    return SignupResponse(
        tenant={"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name},
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
        },
        tokens=TokenResponse(
            access_token=tokens.access_token, refresh_token=tokens.refresh_token
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, svc: Annotated[AuthService, Depends(get_auth_service)]
) -> TokenResponse:
    _, tokens = await svc.login(
        LoginCommand(tenant_slug=body.tenant_slug.lower(), email=body.email, password=body.password)
    )
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(
        user_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
    )
