from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateConversationRequest(BaseModel):
    contact_name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    inbox_id: int
    initial_message: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class ConversationOut(BaseModel):
    id: UUID
    chatwoot_conversation_id: int | None
    contact_name: str
    contact_email: str | None
    inbox_id: int | None
    status: str
