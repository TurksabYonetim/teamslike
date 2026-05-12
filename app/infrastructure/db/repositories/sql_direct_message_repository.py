from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import DirectMessage
from app.domain.ports.repositories import DirectMessageRepository
from app.infrastructure.db.models import DirectMessageModel


def _to_entity(m: DirectMessageModel) -> DirectMessage:
    return DirectMessage(
        id=m.id,
        tenant_id=m.tenant_id,
        sender_user_id=m.sender_user_id,
        recipient_user_id=m.recipient_user_id,
        content=m.content,
        read_at=m.read_at,
        created_at=m.created_at,
    )


class SqlDirectMessageRepository(DirectMessageRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, msg: DirectMessage) -> DirectMessage:
        m = DirectMessageModel(
            id=msg.id,
            tenant_id=msg.tenant_id,
            sender_user_id=msg.sender_user_id,
            recipient_user_id=msg.recipient_user_id,
            content=msg.content,
            read_at=msg.read_at,
            created_at=msg.created_at,
        )
        self._s.add(m)
        await self._s.flush()
        return _to_entity(m)

    async def list_thread(
        self,
        tenant_id: UUID,
        user_a: UUID,
        user_b: UUID,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[DirectMessage]:
        stmt = (
            select(DirectMessageModel)
            .where(
                DirectMessageModel.tenant_id == tenant_id,
                or_(
                    and_(
                        DirectMessageModel.sender_user_id == user_a,
                        DirectMessageModel.recipient_user_id == user_b,
                    ),
                    and_(
                        DirectMessageModel.sender_user_id == user_b,
                        DirectMessageModel.recipient_user_id == user_a,
                    ),
                ),
            )
            .order_by(DirectMessageModel.created_at.asc())
            .limit(limit)
        )
        if since is not None:
            stmt = stmt.where(DirectMessageModel.created_at > since)
        res = await self._s.execute(stmt)
        return [_to_entity(m) for m in res.scalars().all()]

    async def list_threads_for_user(
        self, tenant_id: UUID, user_id: UUID
    ) -> list[tuple[UUID, DirectMessage, int]]:
        # Pull all messages involving this user; group in Python.
        # Volume is small in test/dev; for prod, replace with a window-function query.
        res = await self._s.execute(
            select(DirectMessageModel)
            .where(
                DirectMessageModel.tenant_id == tenant_id,
                or_(
                    DirectMessageModel.sender_user_id == user_id,
                    DirectMessageModel.recipient_user_id == user_id,
                ),
            )
            .order_by(desc(DirectMessageModel.created_at))
        )
        rows = res.scalars().all()
        seen: dict[UUID, DirectMessage] = {}
        unread: dict[UUID, int] = {}
        for m in rows:
            counterparty = (
                m.recipient_user_id if m.sender_user_id == user_id else m.sender_user_id
            )
            if counterparty not in seen:
                seen[counterparty] = _to_entity(m)
            if m.recipient_user_id == user_id and m.read_at is None:
                unread[counterparty] = unread.get(counterparty, 0) + 1
        return [(cp, msg, unread.get(cp, 0)) for cp, msg in seen.items()]

    async def mark_thread_read(
        self, tenant_id: UUID, recipient_user_id: UUID, sender_user_id: UUID
    ) -> int:
        res = await self._s.execute(
            update(DirectMessageModel)
            .where(
                DirectMessageModel.tenant_id == tenant_id,
                DirectMessageModel.recipient_user_id == recipient_user_id,
                DirectMessageModel.sender_user_id == sender_user_id,
                DirectMessageModel.read_at.is_(None),
            )
            .values(read_at=datetime.utcnow())
        )
        return res.rowcount or 0
