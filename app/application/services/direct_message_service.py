from datetime import datetime
from uuid import UUID

from app.application.dto.direct_message import (
    DirectMessageView,
    SendDirectMessageCommand,
    ThreadSummaryView,
)
from app.domain.entities import DirectMessage
from app.domain.exceptions import NotFoundError
from app.domain.ports.unit_of_work import UnitOfWork


def _to_view(m: DirectMessage) -> DirectMessageView:
    return DirectMessageView(
        id=m.id,
        sender_user_id=m.sender_user_id,
        recipient_user_id=m.recipient_user_id,
        content=m.content,
        read_at=m.read_at,
        created_at=m.created_at,
    )


class DirectMessageService:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    async def send(self, cmd: SendDirectMessageCommand) -> DirectMessageView:
        if cmd.sender_user_id == cmd.recipient_user_id:
            raise ValueError("Cannot send a direct message to yourself")
        if not cmd.content.strip():
            raise ValueError("Content cannot be empty")
        async with self._uow as uow:
            recipient = await uow.users.get_by_id(cmd.tenant_id, cmd.recipient_user_id)
            if recipient is None:
                raise NotFoundError("Recipient user not found")
            msg = DirectMessage(
                tenant_id=cmd.tenant_id,
                sender_user_id=cmd.sender_user_id,
                recipient_user_id=cmd.recipient_user_id,
                content=cmd.content,
            )
            saved = await uow.direct_messages.add(msg)
            await uow.commit()
            return _to_view(saved)

    async def list_thread(
        self,
        tenant_id: UUID,
        me: UUID,
        other: UUID,
        since: datetime | None = None,
    ) -> list[DirectMessageView]:
        async with self._uow as uow:
            msgs = await uow.direct_messages.list_thread(
                tenant_id=tenant_id, user_a=me, user_b=other, since=since
            )
            return [_to_view(m) for m in msgs]

    async def list_threads(
        self, tenant_id: UUID, me: UUID
    ) -> list[ThreadSummaryView]:
        async with self._uow as uow:
            rows = await uow.direct_messages.list_threads_for_user(
                tenant_id=tenant_id, user_id=me
            )
            summaries: list[ThreadSummaryView] = []
            for counterparty_id, last_msg, unread_count in rows:
                u = await uow.users.get_by_id(tenant_id, counterparty_id)
                if u is None:
                    continue
                summaries.append(
                    ThreadSummaryView(
                        counterparty_user_id=counterparty_id,
                        counterparty_email=u.email,
                        counterparty_full_name=u.full_name,
                        last_message=_to_view(last_msg),
                        unread_count=unread_count,
                    )
                )
            return summaries

    async def mark_read(
        self, tenant_id: UUID, me: UUID, other: UUID
    ) -> int:
        async with self._uow as uow:
            n = await uow.direct_messages.mark_thread_read(
                tenant_id=tenant_id, recipient_user_id=me, sender_user_id=other
            )
            await uow.commit()
            return n
