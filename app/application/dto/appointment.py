from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class CreateAppointmentCommand:
    tenant_id: UUID
    organizer_user_id: UUID
    title: str
    description: str
    start_at: datetime
    end_at: datetime
    attendee_emails: list[str]
    create_meeting: bool = False


@dataclass
class AppointmentView:
    id: UUID
    title: str
    description: str
    start_at: datetime
    end_at: datetime
    attendee_emails: list[str]
    meeting_id: UUID | None
    status: str
