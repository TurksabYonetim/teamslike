from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TenantOut(BaseModel):
    id: UUID
    slug: str
    name: str
    is_active: bool
    created_at: datetime


class SigningSecretOut(BaseModel):
    tenant_id: UUID
    slug: str
    signing_secret: str
    note: str = (
        "Use this secret to HS256-sign short-lived JWTs for your end-users. "
        "Claims: iss=<tenant_slug>, sub=<your_user_id>, email, name, exp."
    )
