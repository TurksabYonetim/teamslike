from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SendDirectMessageRequest(BaseModel):
    recipient_user_id: UUID
    content: str = Field(min_length=1, max_length=10000)


class DirectMessageOut(BaseModel):
    id: UUID
    sender_user_id: UUID
    recipient_user_id: UUID
    content: str
    read_at: datetime | None
    created_at: datetime


class ThreadCounterpartyOut(BaseModel):
    user_id: UUID
    email: str
    full_name: str


class ThreadSummaryOut(BaseModel):
    counterparty: ThreadCounterpartyOut
    last_message: DirectMessageOut
    unread_count: int


class MarkReadResponse(BaseModel):
    marked: int
