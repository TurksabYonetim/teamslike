from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Conversation, ConversationStatus
from app.domain.ports.repositories import ConversationRepository
from app.infrastructure.db.models import ConversationModel


def _to_entity(m: ConversationModel) -> Conversation:
    return Conversation(
        id=m.id,
        tenant_id=m.tenant_id,
        chatwoot_conversation_id=m.chatwoot_conversation_id,
        contact_name=m.contact_name,
        contact_email=m.contact_email,
        inbox_id=m.inbox_id,
        status=ConversationStatus(m.status),
        created_at=m.created_at,
    )


class SqlConversationRepository(ConversationRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, conversation: Conversation) -> Conversation:
        m = ConversationModel(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            chatwoot_conversation_id=conversation.chatwoot_conversation_id,
            contact_name=conversation.contact_name,
            contact_email=conversation.contact_email,
            inbox_id=conversation.inbox_id,
            status=conversation.status.value,
            created_at=conversation.created_at,
        )
        self._s.add(m)
        await self._s.flush()
        return _to_entity(m)

    async def get_by_id(
        self, tenant_id: UUID, conversation_id: UUID
    ) -> Conversation | None:
        res = await self._s.execute(
            select(ConversationModel).where(
                ConversationModel.tenant_id == tenant_id,
                ConversationModel.id == conversation_id,
            )
        )
        m = res.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_for_tenant(self, tenant_id: UUID) -> list[Conversation]:
        res = await self._s.execute(
            select(ConversationModel)
            .where(ConversationModel.tenant_id == tenant_id)
            .order_by(ConversationModel.created_at.desc())
        )
        return [_to_entity(m) for m in res.scalars().all()]

    async def update(self, conversation: Conversation) -> Conversation:
        m = await self._s.get(ConversationModel, conversation.id)
        if m is None:
            raise KeyError(conversation.id)
        m.status = conversation.status.value
        m.contact_name = conversation.contact_name
        m.contact_email = conversation.contact_email
        await self._s.flush()
        return _to_entity(m)
