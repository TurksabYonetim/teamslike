import secrets
from uuid import UUID

from app.application.dto.meeting import CreateMeetingCommand, MeetingView
from app.domain.entities import Meeting
from app.domain.exceptions import NotFoundError
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.ports.video_provider import VideoProviderPort


class MeetingService:
    def __init__(self, uow: UnitOfWork, video: VideoProviderPort):
        self._uow = uow
        self._video = video

    async def create(self, cmd: CreateMeetingCommand) -> MeetingView:
        room_name = f"{cmd.tenant_slug}-{secrets.token_urlsafe(8)}".lower()
        room = await self._video.create_room(
            room_name=room_name,
            moderator_email=cmd.host_email,
            moderator_name=cmd.host_name,
            tenant_slug=cmd.tenant_slug,
        )

        meeting = Meeting(
            tenant_id=cmd.tenant_id,
            host_user_id=cmd.host_user_id,
            title=cmd.title,
            room_name=room_name,
            scheduled_at=cmd.scheduled_at,
            duration_minutes=cmd.duration_minutes,
        )
        async with self._uow as uow:
            meeting = await uow.meetings.add(meeting)
            await uow.commit()

        return MeetingView(
            id=meeting.id,
            title=meeting.title,
            room_name=meeting.room_name,
            join_url=room.join_url,
            moderator_token=room.moderator_token,
            scheduled_at=meeting.scheduled_at,
            duration_minutes=meeting.duration_minutes,
            status=meeting.status.value,
        )

    async def list_for_tenant(self, tenant_id: UUID) -> list[Meeting]:
        async with self._uow as uow:
            return await uow.meetings.list_for_tenant(tenant_id)

    async def get(self, tenant_id: UUID, meeting_id: UUID) -> Meeting:
        async with self._uow as uow:
            m = await uow.meetings.get_by_id(tenant_id, meeting_id)
            if not m:
                raise NotFoundError("Meeting not found")
            return m

    async def issue_guest_join(
        self, tenant_id: UUID, meeting_id: UUID, tenant_slug: str, guest_name: str
    ) -> tuple[str, str]:
        meeting = await self.get(tenant_id, meeting_id)
        token = await self._video.issue_guest_token(
            room_name=meeting.room_name, guest_name=guest_name, tenant_slug=tenant_slug
        )
        return meeting.room_name, token
