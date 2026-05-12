import secrets
from uuid import UUID

from app.domain.entities import Tenant
from app.domain.exceptions import NotFoundError
from app.domain.ports.unit_of_work import UnitOfWork


def generate_signing_secret() -> str:
    # 32 random bytes -> 43-char URL-safe base64 string
    return secrets.token_urlsafe(32)


class TenantService:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    async def list_all(self) -> list[Tenant]:
        async with self._uow as uow:
            return await uow.tenants.list_all()

    async def get(self, tenant_id: UUID) -> Tenant:
        async with self._uow as uow:
            tenant = await uow.tenants.get_by_id(tenant_id)
            if not tenant:
                raise NotFoundError("Tenant not found")
            return tenant

    async def rotate_signing_secret(self, tenant_id: UUID) -> Tenant:
        async with self._uow as uow:
            tenant = await uow.tenants.get_by_id(tenant_id)
            if not tenant:
                raise NotFoundError("Tenant not found")
            tenant.signing_secret = generate_signing_secret()
            tenant = await uow.tenants.update(tenant)
            await uow.commit()
            return tenant
