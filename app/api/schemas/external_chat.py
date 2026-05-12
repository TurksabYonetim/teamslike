from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TenantSummaryOut(BaseModel):
    tenant_id: UUID
    slug: str
    name: str


class SellerOut(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    role: str
    tenant: TenantSummaryOut


class StartThreadRequest(BaseModel):
    seller_user_id: UUID
    initial_message: str | None = None


class PostMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


# Threads + messages are returned as Chatwoot-shaped dicts (sender, message_type,
# attachments, timestamps); the frontend renders them directly.
ThreadOut = dict[str, Any]
MessageOut = dict[str, Any]
