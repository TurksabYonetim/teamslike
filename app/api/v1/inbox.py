from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_external_chat_service,
)
from app.api.schemas.external_chat import PostMessageRequest
from app.application.services.external_chat_service import ExternalChatService

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("/threads")
async def list_threads(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    """The threads in the *current user's* personal inbox.

    Each user (= seller) has their own per-user inbox; another user in the
    same tenant cannot see threads addressed to this user.
    """
    return await svc.list_inbox_threads_for_user(
        tenant_id=user.tenant_id, user_id=user.user_id
    )


@router.get("/threads/{conversation_id}/messages")
async def list_messages(
    conversation_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    return await svc.list_thread_messages(conversation_id)


@router.post("/threads/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_message(
    conversation_id: int,
    body: PostMessageRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[ExternalChatService, Depends(get_external_chat_service)],
):
    return await svc.post_staff_message(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        conversation_id=conversation_id,
        content=body.content,
    )
