from dataclasses import dataclass
from uuid import UUID


@dataclass
class CreateConversationCommand:
    tenant_id: UUID
    contact_name: str
    contact_email: str | None
    inbox_id: int
    initial_message: str | None = None


@dataclass
class SendMessageCommand:
    tenant_id: UUID
    conversation_id: UUID
    content: str


@dataclass
class ConversationView:
    id: UUID
    chatwoot_conversation_id: int | None
    contact_name: str
    contact_email: str | None
    inbox_id: int | None
    status: str
