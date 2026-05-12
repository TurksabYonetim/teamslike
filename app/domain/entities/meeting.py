from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDED = "ended"
    CANCELLED = "cancelled"


@dataclass
class Meeting:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID | None = None
    host_user_id: UUID | None = None
    title: str = ""
    room_name: str = ""
    scheduled_at: datetime | None = None
    duration_minutes: int = 60
    status: MeetingStatus = MeetingStatus.SCHEDULED
    created_at: datetime = field(default_factory=datetime.utcnow)
