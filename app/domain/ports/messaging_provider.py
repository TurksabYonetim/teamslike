from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MessagingContact:
    id: int
    name: str
    email: str | None
    identifier: str | None = None


@dataclass
class MessagingConversation:
    id: int
    contact_id: int
    inbox_id: int
    status: str


class MessagingProviderPort(ABC):
    @abstractmethod
    async def upsert_contact(
        self, name: str, email: str | None, identifier: str | None = None
    ) -> MessagingContact: ...

    @abstractmethod
    async def create_conversation(
        self, contact_id: int, inbox_id: int, source_id: str | None = None
    ) -> MessagingConversation: ...

    @abstractmethod
    async def send_message(
        self, conversation_id: int, content: str, message_type: str = "outgoing"
    ) -> dict: ...

    @abstractmethod
    async def list_inboxes(self) -> list[dict]: ...

    @abstractmethod
    async def ensure_default_inbox(self, name: str) -> dict: ...

    @abstractmethod
    async def list_conversations_for_contact(self, contact_id: int) -> list[dict]: ...

    @abstractmethod
    async def list_conversations_for_inbox(self, inbox_id: int) -> list[dict]: ...

    @abstractmethod
    async def list_messages(self, conversation_id: int) -> list[dict]: ...
