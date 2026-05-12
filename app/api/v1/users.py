from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_current_user, get_user_service, require_admin
from app.api.schemas.user import CreateUserRequest, UserOut
from app.application.services.user_service import UserService
from app.domain.entities import UserRole

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
async def list_users(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
):
    users = await svc.list_for_tenant(user.tenant_id)
    return [
        UserOut(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.value,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    admin: Annotated[CurrentUser, Depends(require_admin)],
    svc: Annotated[UserService, Depends(get_user_service)],
):
    u = await svc.create(
        tenant_id=admin.tenant_id,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role=UserRole(body.role),
    )
    return UserOut(
        id=u.id,
        tenant_id=u.tenant_id,
        email=u.email,
        full_name=u.full_name,
        role=u.role.value,
        is_active=u.is_active,
        created_at=u.created_at,
    )


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
):
    u = await svc.get(user.tenant_id, user_id)
    return UserOut(
        id=u.id,
        tenant_id=u.tenant_id,
        email=u.email,
        full_name=u.full_name,
        role=u.role.value,
        is_active=u.is_active,
        created_at=u.created_at,
    )
