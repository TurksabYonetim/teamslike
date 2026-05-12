from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Meeting, MeetingStatus
from app.domain.ports.repositories import MeetingRepository
from app.infrastructure.db.models import MeetingModel


def _to_entity(m: MeetingModel) -> Meeting:
    return Meeting(
        id=m.id,
        tenant_id=m.tenant_id,
        host_user_id=m.host_user_id,
        title=m.title,
        room_name=m.room_name,
        scheduled_at=m.scheduled_at,
        duration_minutes=m.duration_minutes,
        status=MeetingStatus(m.status),
        created_at=m.created_at,
    )


class SqlMeetingRepository(MeetingRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, meeting: Meeting) -> Meeting:
        m = MeetingModel(
            id=meeting.id,
            tenant_id=meeting.tenant_id,
            host_user_id=meeting.host_user_id,
            title=meeting.title,
            room_name=meeting.room_name,
            scheduled_at=meeting.scheduled_at,
            duration_minutes=meeting.duration_minutes,
            status=meeting.status.value,
            created_at=meeting.created_at,
        )
        self._s.add(m)
        await self._s.flush()
        return _to_entity(m)

    async def get_by_id(self, tenant_id: UUID, meeting_id: UUID) -> Meeting | None:
        res = await self._s.execute(
            select(MeetingModel).where(
                MeetingModel.tenant_id == tenant_id, MeetingModel.id == meeting_id
            )
        )
        m = res.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_for_tenant(self, tenant_id: UUID) -> list[Meeting]:
        res = await self._s.execute(
            select(MeetingModel)
            .where(MeetingModel.tenant_id == tenant_id)
            .order_by(MeetingModel.scheduled_at.desc().nullslast())
        )
        return [_to_entity(m) for m in res.scalars().all()]

    async def update(self, meeting: Meeting) -> Meeting:
        m = await self._s.get(MeetingModel, meeting.id)
        if m is None:
            raise KeyError(meeting.id)
        m.title = meeting.title
        m.scheduled_at = meeting.scheduled_at
        m.duration_minutes = meeting.duration_minutes
        m.status = meeting.status.value
        await self._s.flush()
        return _to_entity(m)
