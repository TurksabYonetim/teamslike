from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class DirectMessage:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID | None = None
    sender_user_id: UUID | None = None
    recipient_user_id: UUID | None = None
    content: str = ""
    read_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
