from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    CurrentUser,
    get_conversation_service,
    get_current_user,
    get_messaging_provider,
    get_tenant_service,
)
from app.api.schemas.conversation import (
    ConversationOut,
    CreateConversationRequest,
    SendMessageRequest,
)
from app.application.services.tenant_service import TenantService
from app.application.dto.conversation import (
    CreateConversationCommand,
    SendMessageCommand,
)
from app.application.services.conversation_service import ConversationService
from app.domain.ports.messaging_provider import MessagingProviderPort

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
):
    view = await svc.create(
        CreateConversationCommand(
            tenant_id=user.tenant_id,
            contact_name=body.contact_name,
            contact_email=body.contact_email,
            inbox_id=body.inbox_id,
            initial_message=body.initial_message,
        )
    )
    return ConversationOut(**view.__dict__)


@router.get("/", response_model=list[ConversationOut])
async def list_conversations(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
):
    items = await svc.list_for_tenant(user.tenant_id)
    return [
        ConversationOut(
            id=c.id,
            chatwoot_conversation_id=c.chatwoot_conversation_id,
            contact_name=c.contact_name,
            contact_email=c.contact_email,
            inbox_id=c.inbox_id,
            status=c.status.value,
        )
        for c in items
    ]


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
):
    return await svc.send_message(
        SendMessageCommand(
            tenant_id=user.tenant_id,
            conversation_id=conversation_id,
            content=body.content,
        )
    )


@router.get("/inboxes")
async def list_inboxes(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    messaging: Annotated[MessagingProviderPort, Depends(get_messaging_provider)],
):
    return await messaging.list_inboxes()


@router.post("/inboxes/ensure-default")
async def ensure_default_inbox(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    messaging: Annotated[MessagingProviderPort, Depends(get_messaging_provider)],
    tenant_svc: Annotated[TenantService, Depends(get_tenant_service)],
):
    tenant = await tenant_svc.get(user.tenant_id)
    return await messaging.ensure_default_inbox(name=f"teamslike-{tenant.slug}")
