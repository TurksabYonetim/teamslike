from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _to_naive_utc(v: datetime) -> datetime:
    # DB columns are TIMESTAMP WITHOUT TIME ZONE; normalize tz-aware input
    # (e.g. ISO 8601 with "Z") to naive UTC so asyncpg can encode it.
    if v.tzinfo is not None:
        v = v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


class CreateMeetingRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=720)

    _normalize_scheduled_at = field_validator("scheduled_at")(lambda cls, v: _to_naive_utc(v))


class MeetingOut(BaseModel):
    id: UUID
    title: str
    room_name: str
    join_url: str | None = None
    moderator_token: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int
    status: str


class GuestJoinRequest(BaseModel):
    guest_name: str = Field(min_length=1, max_length=255)


class GuestJoinResponse(BaseModel):
    room_name: str
    guest_token: str
    join_url: str
