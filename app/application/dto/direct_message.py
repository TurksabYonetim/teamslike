from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class SendDirectMessageCommand:
    tenant_id: UUID
    sender_user_id: UUID
    recipient_user_id: UUID
    content: str


@dataclass
class DirectMessageView:
    id: UUID
    sender_user_id: UUID
    recipient_user_id: UUID
    content: str
    read_at: datetime | None
    created_at: datetime


@dataclass
class ThreadSummaryView:
    counterparty_user_id: UUID
    counterparty_email: str
    counterparty_full_name: str
    last_message: DirectMessageView
    unread_count: int
