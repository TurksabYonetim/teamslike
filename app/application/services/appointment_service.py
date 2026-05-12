from datetime import datetime
from uuid import UUID

from app.application.dto.appointment import (
    AppointmentView,
    CreateAppointmentCommand,
)
from app.application.dto.meeting import CreateMeetingCommand
from app.application.services.meeting_service import MeetingService
from app.domain.entities import Appointment
from app.domain.exceptions import (
    AppointmentConflictError,
    NotFoundError,
)
from app.domain.ports.unit_of_work import UnitOfWork


class AppointmentService:
    def __init__(self, uow: UnitOfWork, meeting_service: MeetingService):
        self._uow = uow
        self._meetings = meeting_service

    async def create(
        self,
        cmd: CreateAppointmentCommand,
        host_email: str,
        host_name: str,
        tenant_slug: str,
    ) -> AppointmentView:
        if cmd.start_at >= cmd.end_at:
            raise ValueError("start_at must be before end_at")

        async with self._uow as uow:
            conflicts = await uow.appointments.find_overlapping(
                tenant_id=cmd.tenant_id,
                organizer_user_id=cmd.organizer_user_id,
                start_at=cmd.start_at,
                end_at=cmd.end_at,
            )
            if conflicts:
                raise AppointmentConflictError(
                    f"Organizer already has {len(conflicts)} overlapping appointment(s)"
                )

        meeting_id: UUID | None = None
        if cmd.create_meeting:
            mv = await self._meetings.create(
                CreateMeetingCommand(
                    tenant_id=cmd.tenant_id,
                    host_user_id=cmd.organizer_user_id,
                    host_email=host_email,
                    host_name=host_name,
                    tenant_slug=tenant_slug,
                    title=cmd.title,
                    scheduled_at=cmd.start_at,
                    duration_minutes=int(
                        (cmd.end_at - cmd.start_at).total_seconds() // 60
                    ),
                )
            )
            meeting_id = mv.id

        appt = Appointment(
            tenant_id=cmd.tenant_id,
            organizer_user_id=cmd.organizer_user_id,
            title=cmd.title,
            description=cmd.description,
            start_at=cmd.start_at,
            end_at=cmd.end_at,
            attendee_emails=cmd.attendee_emails,
            meeting_id=meeting_id,
        )
        async with self._uow as uow:
            appt = await uow.appointments.add(appt)
            await uow.commit()

        return AppointmentView(
            id=appt.id,
            title=appt.title,
            description=appt.description,
            start_at=appt.start_at,
            end_at=appt.end_at,
            attendee_emails=appt.attendee_emails,
            meeting_id=appt.meeting_id,
            status=appt.status.value,
        )

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Appointment]:
        async with self._uow as uow:
            return await uow.appointments.list_for_tenant(tenant_id, start, end)

    async def get(self, tenant_id: UUID, appointment_id: UUID) -> Appointment:
        async with self._uow as uow:
            a = await uow.appointments.get_by_id(tenant_id, appointment_id)
            if not a:
                raise NotFoundError("Appointment not found")
            return a

    async def delete(self, tenant_id: UUID, appointment_id: UUID) -> None:
        async with self._uow as uow:
            a = await uow.appointments.get_by_id(tenant_id, appointment_id)
            if not a:
                raise NotFoundError("Appointment not found")
            await uow.appointments.delete(tenant_id, appointment_id)
            await uow.commit()
