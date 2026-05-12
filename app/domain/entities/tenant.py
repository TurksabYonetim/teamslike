from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Tenant:
    id: UUID = field(default_factory=uuid4)
    slug: str = ""
    name: str = ""
    is_active: bool = True
    signing_secret: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
