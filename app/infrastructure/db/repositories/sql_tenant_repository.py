from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Tenant
from app.domain.ports.repositories import TenantRepository
from app.infrastructure.db.models import TenantModel


def _to_entity(m: TenantModel) -> Tenant:
    return Tenant(
        id=m.id,
        slug=m.slug,
        name=m.name,
        is_active=m.is_active,
        signing_secret=m.signing_secret or "",
        created_at=m.created_at,
    )


class SqlTenantRepository(TenantRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, tenant: Tenant) -> Tenant:
        m = TenantModel(
            id=tenant.id,
            slug=tenant.slug,
            name=tenant.name,
            is_active=tenant.is_active,
            signing_secret=tenant.signing_secret,
            created_at=tenant.created_at,
        )
        self._s.add(m)
        await self._s.flush()
        return _to_entity(m)

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        m = await self._s.get(TenantModel, tenant_id)
        return _to_entity(m) if m else None

    async def get_by_slug(self, slug: str) -> Tenant | None:
        res = await self._s.execute(select(TenantModel).where(TenantModel.slug == slug))
        m = res.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_all(self) -> list[Tenant]:
        res = await self._s.execute(select(TenantModel).order_by(TenantModel.created_at))
        return [_to_entity(m) for m in res.scalars().all()]

    async def update(self, tenant: Tenant) -> Tenant:
        m = await self._s.get(TenantModel, tenant.id)
        if m is None:
            raise KeyError(tenant.id)
        m.slug = tenant.slug
        m.name = tenant.name
        m.is_active = tenant.is_active
        m.signing_secret = tenant.signing_secret
        await self._s.flush()
        return _to_entity(m)
