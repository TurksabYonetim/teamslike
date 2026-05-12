from app.application.dto.auth import (
    LoginCommand,
    RegisterUserCommand,
    SignupCommand,
    TokenPair,
)
from app.application.security.jwt_helper import AppJWT
from app.application.security.passwords import hash_password, verify_password
from app.application.services.tenant_service import generate_signing_secret
from app.domain.entities import Tenant, User, UserRole
from app.domain.exceptions import (
    AlreadyExistsError,
    InvalidCredentialsError,
    NotFoundError,
    TenantInactiveError,
)
from app.domain.ports.unit_of_work import UnitOfWork


class AuthService:
    def __init__(self, uow: UnitOfWork, jwt_helper: AppJWT):
        self._uow = uow
        self._jwt = jwt_helper

    async def signup(self, cmd: SignupCommand) -> tuple[Tenant, User, TokenPair]:
        async with self._uow as uow:
            existing = await uow.tenants.get_by_slug(cmd.tenant_slug)
            if existing:
                raise AlreadyExistsError(f"Tenant '{cmd.tenant_slug}' already exists")

            tenant = Tenant(
                slug=cmd.tenant_slug,
                name=cmd.tenant_name,
                signing_secret=generate_signing_secret(),
            )
            tenant = await uow.tenants.add(tenant)

            user = User(
                tenant_id=tenant.id,
                email=cmd.admin_email.lower(),
                hashed_password=hash_password(cmd.admin_password),
                full_name=cmd.admin_full_name,
                role=UserRole.OWNER,
            )
            user = await uow.users.add(user)
            await uow.commit()

        tokens = self._issue_tokens(user)
        return tenant, user, tokens

    async def register_user(self, cmd: RegisterUserCommand) -> tuple[Tenant, User, TokenPair]:
        async with self._uow as uow:
            tenant = await uow.tenants.get_by_id(cmd.tenant_id)
            if not tenant:
                raise NotFoundError("Tenant not found")
            if not tenant.is_active:
                raise TenantInactiveError("Tenant is not active")

            existing = await uow.users.get_by_email(tenant.id, cmd.email.lower())
            if existing:
                raise AlreadyExistsError("User with this email already exists")

            user = User(
                tenant_id=tenant.id,
                email=cmd.email.lower(),
                hashed_password=hash_password(cmd.password),
                full_name=cmd.full_name,
                role=UserRole.MEMBER,
            )
            user = await uow.users.add(user)
            await uow.commit()

        tokens = self._issue_tokens(user)
        return tenant, user, tokens

    async def login(self, cmd: LoginCommand) -> tuple[User, TokenPair]:
        async with self._uow as uow:
            tenant = await uow.tenants.get_by_slug(cmd.tenant_slug)
            if not tenant:
                raise NotFoundError("Tenant not found")
            if not tenant.is_active:
                raise TenantInactiveError("Tenant is not active")

            user = await uow.users.get_by_email(tenant.id, cmd.email.lower())
            if not user or not verify_password(cmd.password, user.hashed_password):
                raise InvalidCredentialsError("Invalid email or password")
            if not user.is_active:
                raise InvalidCredentialsError("User is not active")

        tokens = self._issue_tokens(user)
        return user, tokens

    def _issue_tokens(self, user: User) -> TokenPair:
        access = self._jwt.create_access_token(
            user_id=user.id, tenant_id=user.tenant_id, role=user.role.value, email=user.email
        )
        refresh = self._jwt.create_refresh_token(user_id=user.id, tenant_id=user.tenant_id)
        return TokenPair(access_token=access, refresh_token=refresh)
