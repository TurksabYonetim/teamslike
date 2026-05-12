from dataclasses import dataclass
from uuid import UUID


@dataclass
class SignupCommand:
    tenant_slug: str
    tenant_name: str
    admin_email: str
    admin_full_name: str
    admin_password: str


@dataclass
class LoginCommand:
    tenant_slug: str
    email: str
    password: str


@dataclass
class RegisterUserCommand:
    tenant_id: UUID
    email: str
    full_name: str
    password: str


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
