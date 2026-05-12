from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


def _to_naive_utc(v: datetime) -> datetime:
    # DB columns are TIMESTAMP WITHOUT TIME ZONE; normalize tz-aware input
    # (e.g. ISO 8601 with "Z") to naive UTC so asyncpg can encode it.
    if v.tzinfo is not None:
        v = v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


class CreateAppointmentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    start_at: datetime
    end_at: datetime
    attendee_emails: list[EmailStr] = Field(default_factory=list)
    create_meeting: bool = False

    _normalize_start = field_validator("start_at")(lambda cls, v: _to_naive_utc(v))
    _normalize_end = field_validator("end_at")(lambda cls, v: _to_naive_utc(v))


class AppointmentOut(BaseModel):
    id: UUID
    title: str
    description: str
    start_at: datetime
    end_at: datetime
    attendee_emails: list[str]
    meeting_id: UUID | None
    status: str
