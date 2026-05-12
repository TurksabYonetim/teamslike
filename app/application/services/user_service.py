from uuid import UUID

from app.application.security.passwords import hash_password
from app.domain.entities import User, UserRole
from app.domain.exceptions import AlreadyExistsError, NotFoundError
from app.domain.ports.unit_of_work import UnitOfWork


class UserService:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    async def list_for_tenant(self, tenant_id: UUID) -> list[User]:
        async with self._uow as uow:
            return await uow.users.list_for_tenant(tenant_id)

    async def get(self, tenant_id: UUID, user_id: UUID) -> User:
        async with self._uow as uow:
            user = await uow.users.get_by_id(tenant_id, user_id)
            if not user:
                raise NotFoundError("User not found")
            return user

    async def create(
        self,
        tenant_id: UUID,
        email: str,
        full_name: str,
        password: str,
        role: UserRole = UserRole.MEMBER,
    ) -> User:
        async with self._uow as uow:
            existing = await uow.users.get_by_email(tenant_id, email.lower())
            if existing:
                raise AlreadyExistsError("User with this email already exists")
            user = User(
                tenant_id=tenant_id,
                email=email.lower(),
                hashed_password=hash_password(password),
                full_name=full_name,
                role=role,
            )
            user = await uow.users.add(user)
            await uow.commit()
            return user
