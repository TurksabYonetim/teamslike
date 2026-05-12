from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class Appointment:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID | None = None
    organizer_user_id: UUID | None = None
    title: str = ""
    description: str = ""
    start_at: datetime | None = None
    end_at: datetime | None = None
    attendee_emails: list[str] = field(default_factory=list)
    meeting_id: UUID | None = None
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    created_at: datetime = field(default_factory=datetime.utcnow)
