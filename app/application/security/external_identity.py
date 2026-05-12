from dataclasses import dataclass
from uuid import UUID


@dataclass
class ExternalIdentity:
    """End-user identity proven by a tenant-signed JWT.

    Stateless: not persisted in our DB. The tenant signs a short-lived JWT
    with its `signing_secret`; we verify it and surface the claims.
    """

    tenant_id: UUID
    tenant_slug: str
    external_sub: str
    email: str
    name: str
