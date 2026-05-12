from uuid import UUID

from app.application.dto.conversation import (
    ConversationView,
    CreateConversationCommand,
    SendMessageCommand,
)
from app.domain.entities import Conversation
from app.domain.exceptions import NotFoundError
from app.domain.ports.messaging_provider import MessagingProviderPort
from app.domain.ports.unit_of_work import UnitOfWork


class ConversationService:
    def __init__(self, uow: UnitOfWork, messaging: MessagingProviderPort):
        self._uow = uow
        self._messaging = messaging

    async def create(self, cmd: CreateConversationCommand) -> ConversationView:
        contact = await self._messaging.upsert_contact(
            name=cmd.contact_name,
            email=cmd.contact_email,
            identifier=f"{cmd.tenant_id}:{cmd.contact_email or cmd.contact_name}",
        )
        cw_conv = await self._messaging.create_conversation(
            contact_id=contact.id, inbox_id=cmd.inbox_id
        )
        if cmd.initial_message:
            await self._messaging.send_message(cw_conv.id, cmd.initial_message)

        conv = Conversation(
            tenant_id=cmd.tenant_id,
            chatwoot_conversation_id=cw_conv.id,
            contact_name=cmd.contact_name,
            contact_email=cmd.contact_email,
            inbox_id=cmd.inbox_id,
        )
        async with self._uow as uow:
            conv = await uow.conversations.add(conv)
            await uow.commit()

        return ConversationView(
            id=conv.id,
            chatwoot_conversation_id=conv.chatwoot_conversation_id,
            contact_name=conv.contact_name,
            contact_email=conv.contact_email,
            inbox_id=conv.inbox_id,
            status=conv.status.value,
        )

    async def send_message(self, cmd: SendMessageCommand) -> dict:
        async with self._uow as uow:
            conv = await uow.conversations.get_by_id(cmd.tenant_id, cmd.conversation_id)
            if not conv or conv.chatwoot_conversation_id is None:
                raise NotFoundError("Conversation not found")
        return await self._messaging.send_message(
            conv.chatwoot_conversation_id, cmd.content
        )

    async def list_for_tenant(self, tenant_id: UUID) -> list[Conversation]:
        async with self._uow as uow:
            return await uow.conversations.list_for_tenant(tenant_id)
