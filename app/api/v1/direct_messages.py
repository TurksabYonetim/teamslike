from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_direct_message_service,
)
from app.api.schemas.direct_message import (
    DirectMessageOut,
    MarkReadResponse,
    SendDirectMessageRequest,
    ThreadCounterpartyOut,
    ThreadSummaryOut,
)
from app.application.dto.direct_message import SendDirectMessageCommand
from app.application.services.direct_message_service import DirectMessageService

router = APIRouter(prefix="/dm", tags=["direct-messages"])


def _naive_utc(v: datetime | None) -> datetime | None:
    if v is None or v.tzinfo is None:
        return v
    return v.astimezone(timezone.utc).replace(tzinfo=None)


def _msg_to_out(m) -> DirectMessageOut:
    return DirectMessageOut(
        id=m.id,
        sender_user_id=m.sender_user_id,
        recipient_user_id=m.recipient_user_id,
        content=m.content,
        read_at=m.read_at,
        created_at=m.created_at,
    )


@router.post("/messages", response_model=DirectMessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    body: SendDirectMessageRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[DirectMessageService, Depends(get_direct_message_service)],
):
    view = await svc.send(
        SendDirectMessageCommand(
            tenant_id=user.tenant_id,
            sender_user_id=user.user_id,
            recipient_user_id=body.recipient_user_id,
            content=body.content,
        )
    )
    return _msg_to_out(view)


@router.get("/threads/{other_user_id}/messages", response_model=list[DirectMessageOut])
async def list_thread(
    other_user_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[DirectMessageService, Depends(get_direct_message_service)],
    since: datetime | None = Query(default=None),
):
    msgs = await svc.list_thread(
        tenant_id=user.tenant_id,
        me=user.user_id,
        other=other_user_id,
        since=_naive_utc(since),
    )
    return [_msg_to_out(m) for m in msgs]


@router.post("/threads/{other_user_id}/read", response_model=MarkReadResponse)
async def mark_thread_read(
    other_user_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[DirectMessageService, Depends(get_direct_message_service)],
):
    n = await svc.mark_read(tenant_id=user.tenant_id, me=user.user_id, other=other_user_id)
    return MarkReadResponse(marked=n)


@router.get("/threads", response_model=list[ThreadSummaryOut])
async def list_threads(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[DirectMessageService, Depends(get_direct_message_service)],
):
    items = await svc.list_threads(tenant_id=user.tenant_id, me=user.user_id)
    return [
        ThreadSummaryOut(
            counterparty=ThreadCounterpartyOut(
                user_id=t.counterparty_user_id,
                email=t.counterparty_email,
                full_name=t.counterparty_full_name,
            ),
            last_message=_msg_to_out(t.last_message),
            unread_count=t.unread_count,
        )
        for t in items
    ]
