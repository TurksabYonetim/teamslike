from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_tenant_service,
    require_admin,
)
from app.api.schemas.tenant import SigningSecretOut, TenantOut
from app.application.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantOut)
async def my_tenant(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantOut:
    t = await svc.get(user.tenant_id)
    return TenantOut(
        id=t.id, slug=t.slug, name=t.name, is_active=t.is_active, created_at=t.created_at
    )


@router.get("/me/signing-secret", response_model=SigningSecretOut)
async def get_signing_secret(
    admin: Annotated[CurrentUser, Depends(require_admin)],
    svc: Annotated[TenantService, Depends(get_tenant_service)],
) -> SigningSecretOut:
    t = await svc.get(admin.tenant_id)
    return SigningSecretOut(tenant_id=t.id, slug=t.slug, signing_secret=t.signing_secret)


@router.post("/me/rotate-signing-secret", response_model=SigningSecretOut)
async def rotate_signing_secret(
    admin: Annotated[CurrentUser, Depends(require_admin)],
    svc: Annotated[TenantService, Depends(get_tenant_service)],
) -> SigningSecretOut:
    t = await svc.rotate_signing_secret(admin.tenant_id)
    return SigningSecretOut(tenant_id=t.id, slug=t.slug, signing_secret=t.signing_secret)
