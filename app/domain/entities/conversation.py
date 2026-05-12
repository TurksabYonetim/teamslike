from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class ConversationStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"


@dataclass
class Conversation:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID | None = None
    chatwoot_conversation_id: int | None = None
    contact_name: str = ""
    contact_email: str | None = None
    inbox_id: int | None = None
    status: ConversationStatus = ConversationStatus.OPEN
    created_at: datetime = field(default_factory=datetime.utcnow)
