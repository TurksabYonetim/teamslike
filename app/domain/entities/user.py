from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


@dataclass
class User:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID | None = None
    email: str = ""
    hashed_password: str = ""
    full_name: str = ""
    role: UserRole = UserRole.MEMBER
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
