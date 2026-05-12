from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_meeting_service,
    get_tenant_service,
)
from app.api.schemas.meeting import (
    CreateMeetingRequest,
    GuestJoinRequest,
    GuestJoinResponse,
    MeetingOut,
)
from app.application.dto.meeting import CreateMeetingCommand
from app.application.services.meeting_service import MeetingService
from app.application.services.tenant_service import TenantService

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    body: CreateMeetingRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[MeetingService, Depends(get_meeting_service)],
    tenant_svc: Annotated[TenantService, Depends(get_tenant_service)],
):
    tenant = await tenant_svc.get(user.tenant_id)
    view = await svc.create(
        CreateMeetingCommand(
            tenant_id=user.tenant_id,
            host_user_id=user.user_id,
            host_email=user.email,
            host_name=user.email.split("@")[0],
            tenant_slug=tenant.slug,
            title=body.title,
            scheduled_at=body.scheduled_at,
            duration_minutes=body.duration_minutes,
        )
    )
    return MeetingOut(
        id=view.id,
        title=view.title,
        room_name=view.room_name,
        join_url=view.join_url,
        moderator_token=view.moderator_token,
        scheduled_at=view.scheduled_at,
        duration_minutes=view.duration_minutes,
        status=view.status,
    )


@router.get("/", response_model=list[MeetingOut])
async def list_meetings(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[MeetingService, Depends(get_meeting_service)],
):
    meetings = await svc.list_for_tenant(user.tenant_id)
    return [
        MeetingOut(
            id=m.id,
            title=m.title,
            room_name=m.room_name,
            scheduled_at=m.scheduled_at,
            duration_minutes=m.duration_minutes,
            status=m.status.value,
        )
        for m in meetings
    ]


@router.post("/{meeting_id}/guest-token", response_model=GuestJoinResponse)
async def guest_token(
    meeting_id: UUID,
    body: GuestJoinRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[MeetingService, Depends(get_meeting_service)],
    tenant_svc: Annotated[TenantService, Depends(get_tenant_service)],
):
    tenant = await tenant_svc.get(user.tenant_id)
    room_name, token = await svc.issue_guest_join(
        tenant_id=user.tenant_id,
        meeting_id=meeting_id,
        tenant_slug=tenant.slug,
        guest_name=body.guest_name,
    )
    from app.infrastructure.config import get_settings

    base = get_settings().jitsi_public_url.rstrip("/")
    return GuestJoinResponse(
        room_name=room_name, guest_token=token, join_url=f"{base}/{room_name}?jwt={token}"
    )
