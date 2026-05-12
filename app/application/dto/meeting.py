from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class CreateMeetingCommand:
    tenant_id: UUID
    host_user_id: UUID
    host_email: str
    host_name: str
    tenant_slug: str
    title: str
    scheduled_at: datetime
    duration_minutes: int = 60


@dataclass
class MeetingView:
    id: UUID
    title: str
    room_name: str
    join_url: str
    moderator_token: str | None
    scheduled_at: datetime
    duration_minutes: int
    status: str
