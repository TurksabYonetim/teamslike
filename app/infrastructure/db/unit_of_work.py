from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.ports.unit_of_work import UnitOfWork
from app.infrastructure.db.repositories.sql_appointment_repository import (
    SqlAppointmentRepository,
)
from app.infrastructure.db.repositories.sql_conversation_repository import (
    SqlConversationRepository,
)
from app.infrastructure.db.repositories.sql_direct_message_repository import (
    SqlDirectMessageRepository,
)
from app.infrastructure.db.repositories.sql_meeting_repository import (
    SqlMeetingRepository,
)
from app.infrastructure.db.repositories.sql_tenant_repository import (
    SqlTenantRepository,
)
from app.infrastructure.db.repositories.sql_user_repository import SqlUserRepository


class SqlUnitOfWork(UnitOfWork):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sessionmaker
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlUnitOfWork":
        self._session = self._sessionmaker()
        self.tenants = SqlTenantRepository(self._session)
        self.users = SqlUserRepository(self._session)
        self.meetings = SqlMeetingRepository(self._session)
        self.conversations = SqlConversationRepository(self._session)
        self.appointments = SqlAppointmentRepository(self._session)
        self.direct_messages = SqlDirectMessageRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UoW not entered")
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("UoW not entered")
        await self._session.rollback()
