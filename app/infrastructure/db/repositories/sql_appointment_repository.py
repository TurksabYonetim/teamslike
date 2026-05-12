from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Appointment, AppointmentStatus
from app.domain.ports.repositories import AppointmentRepository
from app.infrastructure.db.models import AppointmentModel


def _to_entity(m: AppointmentModel) -> Appointment:
    return Appointment(
        id=m.id,
        tenant_id=m.tenant_id,
        organizer_user_id=m.organizer_user_id,
        title=m.title,
        description=m.description,
        start_at=m.start_at,
        end_at=m.end_at,
        attendee_emails=list(m.attendee_emails or []),
        meeting_id=m.meeting_id,
        status=AppointmentStatus(m.status),
        created_at=m.created_at,
    )


class SqlAppointmentRepository(AppointmentRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, appointment: Appointment) -> Appointment:
        m = AppointmentModel(
            id=appointment.id,
            tenant_id=appointment.tenant_id,
            organizer_user_id=appointment.organizer_user_id,
            title=appointment.title,
            description=appointment.description,
            start_at=appointment.start_at,
            end_at=appointment.end_at,
            attendee_emails=appointment.attendee_emails,
            meeting_id=appointment.meeting_id,
            status=appointment.status.value,
            created_at=appointment.created_at,
        )
        self._s.add(m)
        await self._s.flush()
        return _to_entity(m)

    async def get_by_id(
        self, tenant_id: UUID, appointment_id: UUID
    ) -> Appointment | None:
        res = await self._s.execute(
            select(AppointmentModel).where(
                AppointmentModel.tenant_id == tenant_id,
                AppointmentModel.id == appointment_id,
            )
        )
        m = res.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Appointment]:
        stmt = select(AppointmentModel).where(AppointmentModel.tenant_id == tenant_id)
        if start is not None:
            stmt = stmt.where(AppointmentModel.end_at >= start)
        if end is not None:
            stmt = stmt.where(AppointmentModel.start_at <= end)
        stmt = stmt.order_by(AppointmentModel.start_at)
        res = await self._s.execute(stmt)
        return [_to_entity(m) for m in res.scalars().all()]

    async def find_overlapping(
        self,
        tenant_id: UUID,
        organizer_user_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | None = None,
    ) -> list[Appointment]:
        conditions = [
            AppointmentModel.tenant_id == tenant_id,
            AppointmentModel.organizer_user_id == organizer_user_id,
            AppointmentModel.status != AppointmentStatus.CANCELLED.value,
            AppointmentModel.start_at < end_at,
            AppointmentModel.end_at > start_at,
        ]
        if exclude_id is not None:
            conditions.append(AppointmentModel.id != exclude_id)
        res = await self._s.execute(select(AppointmentModel).where(and_(*conditions)))
        return [_to_entity(m) for m in res.scalars().all()]

    async def update(self, appointment: Appointment) -> Appointment:
        m = await self._s.get(AppointmentModel, appointment.id)
        if m is None:
            raise KeyError(appointment.id)
        m.title = appointment.title
        m.description = appointment.description
        m.start_at = appointment.start_at
        m.end_at = appointment.end_at
        m.attendee_emails = appointment.attendee_emails
        m.status = appointment.status.value
        m.meeting_id = appointment.meeting_id
        await self._s.flush()
        return _to_entity(m)

    async def delete(self, tenant_id: UUID, appointment_id: UUID) -> None:
        await self._s.execute(
            delete(AppointmentModel).where(
                AppointmentModel.tenant_id == tenant_id,
                AppointmentModel.id == appointment_id,
            )
        )
