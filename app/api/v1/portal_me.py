from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.api.deps import get_external_chat_service, get_external_identity
from app.api.schemas.external_chat import (
    PostMessageRequest,
    SellerOut,
    StartThreadRequest,
    TenantSummaryOut,
)
from app.application.security.external_identity import ExternalIdentity
from app.application.services.external_chat_service import ExternalChatService

router = APIRouter(prefix="/portal/me", tags=["portal"])


@router.get("/whoami")
async def whoami(
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
):
    return {
        "tenant_id": str(identity.tenant_id),
        "tenant_slug": identity.tenant_slug,
        "external_sub": identity.external_sub,
        "email": identity.email,
        "name": identity.name,
    }


@router.get("/tenants", response_model=list[TenantSummaryOut])
async def list_tenants(
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    tenants = await svc.list_tenants()
    return [TenantSummaryOut(tenant_id=t.id, slug=t.slug, name=t.name) for t in tenants]


@router.get("/sellers", response_model=list[SellerOut])
async def list_sellers(
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
    tenant_id: UUID | None = Query(default=None),
):
    pairs = await svc.list_sellers(tenant_id=tenant_id)
    return [
        SellerOut(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.value,
            tenant=TenantSummaryOut(tenant_id=t.id, slug=t.slug, name=t.name),
        )
        for u, t in pairs
    ]


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def start_thread(
    body: StartThreadRequest,
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    return await svc.get_or_create_thread_for_identity(
        identity=identity,
        seller_user_id=body.seller_user_id,
        initial_message=body.initial_message,
    )


@router.get("/threads")
async def list_threads(
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    return await svc.list_threads_for_identity(identity)


@router.get("/threads/{conversation_id}/messages")
async def list_messages(
    conversation_id: int,
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    return await svc.list_thread_messages(conversation_id)


@router.post("/threads/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_message(
    conversation_id: int,
    body: PostMessageRequest,
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    return await svc.post_message_as_external(
        identity=identity,
        conversation_id=conversation_id,
        content=body.content,
    )


@router.post("/threads/{conversation_id}/attachments", status_code=status.HTTP_201_CREATED)
async def post_attachment(
    conversation_id: int,
    identity: Annotated[ExternalIdentity, Depends(get_external_identity)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
    file: UploadFile = File(...),
    content: Annotated[str, Form()] = "",
):
    # Tek dosya/istek. Çoklu yükleme için frontend ardışık istek atar.
    data = await file.read()
    attachments = [(file.filename or "file", data, file.content_type or "application/octet-stream")]
    return await svc.post_message_as_external(
        identity=identity,
        conversation_id=conversation_id,
        content=content,
        attachments=attachments,
    )
