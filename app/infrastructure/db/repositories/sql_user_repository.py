from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import User, UserRole
from app.domain.ports.repositories import UserRepository
from app.infrastructure.db.models import UserModel


def _to_entity(m: UserModel) -> User:
    return User(
        id=m.id,
        tenant_id=m.tenant_id,
        email=m.email,
        hashed_password=m.hashed_password,
        full_name=m.full_name,
        role=UserRole(m.role),
        is_active=m.is_active,
        created_at=m.created_at,
    )


class SqlUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, user: User) -> User:
        m = UserModel(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            hashed_password=user.hashed_password,
            full_name=user.full_name,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        self._s.add(m)
        await self._s.flush()
        return _to_entity(m)

    async def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None:
        res = await self._s.execute(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id, UserModel.id == user_id
            )
        )
        m = res.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        res = await self._s.execute(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id, UserModel.email == email
            )
        )
        m = res.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_for_tenant(self, tenant_id: UUID) -> list[User]:
        res = await self._s.execute(
            select(UserModel)
            .where(UserModel.tenant_id == tenant_id)
            .order_by(UserModel.created_at)
        )
        return [_to_entity(m) for m in res.scalars().all()]
