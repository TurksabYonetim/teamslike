from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.ports.repositories import (
    AppointmentRepository,
    ConversationRepository,
    DirectMessageRepository,
    MeetingRepository,
    TenantRepository,
    UserRepository,
)


class UnitOfWork(ABC):
    tenants: TenantRepository
    users: UserRepository
    meetings: MeetingRepository
    conversations: ConversationRepository
    appointments: AppointmentRepository
    direct_messages: DirectMessageRepository

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork": ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
