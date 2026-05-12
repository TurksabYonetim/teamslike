from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities import (
    Appointment,
    Conversation,
    DirectMessage,
    Meeting,
    Tenant,
    User,
)


class TenantRepository(ABC):
    @abstractmethod
    async def add(self, tenant: Tenant) -> Tenant: ...

    @abstractmethod
    async def get_by_id(self, tenant_id: UUID) -> Tenant | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Tenant | None: ...

    @abstractmethod
    async def list_all(self) -> list[Tenant]: ...

    @abstractmethod
    async def update(self, tenant: Tenant) -> Tenant: ...


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> User: ...

    @abstractmethod
    async def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None: ...

    @abstractmethod
    async def list_for_tenant(self, tenant_id: UUID) -> list[User]: ...


class MeetingRepository(ABC):
    @abstractmethod
    async def add(self, meeting: Meeting) -> Meeting: ...

    @abstractmethod
    async def get_by_id(self, tenant_id: UUID, meeting_id: UUID) -> Meeting | None: ...

    @abstractmethod
    async def list_for_tenant(self, tenant_id: UUID) -> list[Meeting]: ...

    @abstractmethod
    async def update(self, meeting: Meeting) -> Meeting: ...


class ConversationRepository(ABC):
    @abstractmethod
    async def add(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    async def get_by_id(
        self, tenant_id: UUID, conversation_id: UUID
    ) -> Conversation | None: ...

    @abstractmethod
    async def list_for_tenant(self, tenant_id: UUID) -> list[Conversation]: ...

    @abstractmethod
    async def update(self, conversation: Conversation) -> Conversation: ...


class AppointmentRepository(ABC):
    @abstractmethod
    async def add(self, appointment: Appointment) -> Appointment: ...

    @abstractmethod
    async def get_by_id(
        self, tenant_id: UUID, appointment_id: UUID
    ) -> Appointment | None: ...

    @abstractmethod
    async def list_for_tenant(
        self,
        tenant_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Appointment]: ...

    @abstractmethod
    async def find_overlapping(
        self,
        tenant_id: UUID,
        organizer_user_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | None = None,
    ) -> list[Appointment]: ...

    @abstractmethod
    async def update(self, appointment: Appointment) -> Appointment: ...

    @abstractmethod
    async def delete(self, tenant_id: UUID, appointment_id: UUID) -> None: ...


class DirectMessageRepository(ABC):
    @abstractmethod
    async def add(self, msg: DirectMessage) -> DirectMessage: ...

    @abstractmethod
    async def list_thread(
        self,
        tenant_id: UUID,
        user_a: UUID,
        user_b: UUID,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[DirectMessage]: ...

    @abstractmethod
    async def list_threads_for_user(
        self, tenant_id: UUID, user_id: UUID
    ) -> list[tuple[UUID, DirectMessage, int]]:
        """Returns list of (counterparty_user_id, last_message, unread_count)."""

    @abstractmethod
    async def mark_thread_read(
        self, tenant_id: UUID, recipient_user_id: UUID, sender_user_id: UUID
    ) -> int: ...
