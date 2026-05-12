from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    CurrentUser,
    get_appointment_service,
    get_current_user,
    get_tenant_service,
)
from app.api.schemas.appointment import AppointmentOut, CreateAppointmentRequest


def _naive_utc(v: datetime | None) -> datetime | None:
    if v is None or v.tzinfo is None:
        return v
    return v.astimezone(timezone.utc).replace(tzinfo=None)
from app.application.dto.appointment import CreateAppointmentCommand
from app.application.services.appointment_service import AppointmentService
from app.application.services.tenant_service import TenantService

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("/", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: CreateAppointmentRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[AppointmentService, Depends(get_appointment_service)],
    tenant_svc: Annotated[TenantService, Depends(get_tenant_service)],
):
    tenant = await tenant_svc.get(user.tenant_id)
    view = await svc.create(
        CreateAppointmentCommand(
            tenant_id=user.tenant_id,
            organizer_user_id=user.user_id,
            title=body.title,
            description=body.description,
            start_at=body.start_at,
            end_at=body.end_at,
            attendee_emails=[str(e) for e in body.attendee_emails],
            create_meeting=body.create_meeting,
        ),
        host_email=user.email,
        host_name=user.email.split("@")[0],
        tenant_slug=tenant.slug,
    )
    return AppointmentOut(**view.__dict__)


@router.get("/", response_model=list[AppointmentOut])
async def list_appointments(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[AppointmentService, Depends(get_appointment_service)],
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
):
    items = await svc.list_for_tenant(user.tenant_id, _naive_utc(start), _naive_utc(end))
    return [
        AppointmentOut(
            id=a.id,
            title=a.title,
            description=a.description,
            start_at=a.start_at,
            end_at=a.end_at,
            attendee_emails=a.attendee_emails,
            meeting_id=a.meeting_id,
            status=a.status.value,
        )
        for a in items
    ]


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    appointment_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[AppointmentService, Depends(get_appointment_service)],
):
    await svc.delete(user.tenant_id, appointment_id)
