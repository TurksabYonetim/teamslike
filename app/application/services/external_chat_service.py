from uuid import UUID

from app.application.security.external_identity import ExternalIdentity
from app.domain.entities import Tenant, User
from app.domain.exceptions import NotFoundError
from app.domain.ports.messaging_provider import MessagingProviderPort
from app.domain.ports.unit_of_work import UnitOfWork


# Inbox naming: each User (= seller) has their own Chatwoot inbox.
# The user's UUID (no dashes) lives in the inbox name so we can resolve
# inbox -> user without an extra lookup.
_USER_INBOX_PREFIX = "teamslike-u-"


def _user_inbox_name(user: User) -> str:
    return _USER_INBOX_PREFIX + user.id.hex


def _user_uuid_from_inbox_name(name: str) -> UUID | None:
    if not name.startswith(_USER_INBOX_PREFIX):
        return None
    suffix = name[len(_USER_INBOX_PREFIX) :]
    try:
        return UUID(hex=suffix)
    except ValueError:
        return None


def _identifier(tenant_slug: str, external_sub: str) -> str:
    return f"{tenant_slug}:{external_sub}"


class ExternalChatService:
    """
    Tenant-staff ↔ external-user messaging on Chatwoot. Stateless on our side.

    Mapping:
      - End user (proven by tenant-signed JWT) -> Chatwoot Contact
        (identifier: "<tenant_slug>:<external_sub>")
      - User (seller; staff member of a tenant)  -> Chatwoot Inbox
        (one auto-provisioned per user, named "teamslike-u-<user_uuid>")
      - Thread between an end user and a seller -> Chatwoot Conversation
        in that seller's inbox, with that contact

    A tenant is just a grouping of sellers; routing is per-user, so two
    sellers in the same tenant don't see each other's customer threads.
    """

    def __init__(self, uow: UnitOfWork, messaging: MessagingProviderPort):
        self._uow = uow
        self._messaging = messaging

    # ------- helpers -------
    async def _ensure_chatwoot_contact(
        self, tenant_slug: str, external_sub: str, name: str, email: str
    ) -> int:
        mc = await self._messaging.upsert_contact(
            name=name or external_sub,
            email=email or None,
            identifier=_identifier(tenant_slug, external_sub),
        )
        return mc.id

    async def _ensure_user_inbox(self, user: User) -> int:
        ib = await self._messaging.ensure_default_inbox(name=_user_inbox_name(user))
        return int(ib["id"])

    async def _resolve_tenant(self, tenant_id: UUID) -> Tenant:
        async with self._uow as uow:
            tenant = await uow.tenants.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found")
        return tenant

    async def _resolve_user(self, user_id: UUID) -> tuple[User, Tenant]:
        # We don't know which tenant the user belongs to up front; iterate
        # tenants until we find them. There's no get_user_global yet.
        async with self._uow as uow:
            tenants = await uow.tenants.list_all()
            for t in tenants:
                u = await uow.users.get_by_id(t.id, user_id)
                if u is not None:
                    return u, t
        raise NotFoundError("User not found")

    # ------- end-user (portal) view -------
    async def list_tenants(self) -> list[Tenant]:
        async with self._uow as uow:
            return await uow.tenants.list_all()

    async def list_sellers(
        self, tenant_id: UUID | None = None
    ) -> list[tuple[User, Tenant]]:
        async with self._uow as uow:
            tenants = await uow.tenants.list_all()
            out: list[tuple[User, Tenant]] = []
            for t in tenants:
                if tenant_id is not None and t.id != tenant_id:
                    continue
                users = await uow.users.list_for_tenant(t.id)
                for u in users:
                    if u.is_active:
                        out.append((u, t))
        return out

    async def get_or_create_thread_for_identity(
        self,
        identity: ExternalIdentity,
        seller_user_id: UUID,
        initial_message: str | None = None,
    ) -> dict:
        seller, tenant = await self._resolve_user(seller_user_id)
        contact_id = await self._ensure_chatwoot_contact(
            tenant_slug=identity.tenant_slug,
            external_sub=identity.external_sub,
            name=identity.name,
            email=identity.email,
        )
        inbox_id = await self._ensure_user_inbox(seller)

        existing = await self._messaging.list_conversations_for_contact(contact_id)
        for c in existing:
            if c.get("inbox_id") == inbox_id:
                if initial_message:
                    await self._messaging.send_message(
                        conversation_id=int(c["id"]),
                        content=initial_message,
                        message_type="incoming",
                    )
                return self._enrich_thread(c, seller, tenant)

        conv = await self._messaging.create_conversation(
            contact_id=contact_id,
            inbox_id=inbox_id,
            source_id=_identifier(identity.tenant_slug, identity.external_sub),
        )
        if initial_message:
            await self._messaging.send_message(
                conversation_id=int(conv.id),
                content=initial_message,
                message_type="incoming",
            )
        return self._enrich_thread(
            {"id": conv.id, "inbox_id": conv.inbox_id, "status": conv.status},
            seller,
            tenant,
        )

    async def list_threads_for_identity(self, identity: ExternalIdentity) -> list[dict]:
        contact_id = await self._ensure_chatwoot_contact(
            tenant_slug=identity.tenant_slug,
            external_sub=identity.external_sub,
            name=identity.name,
            email=identity.email,
        )
        inboxes = await self._messaging.list_inboxes()

        # Build inbox_id -> (User, Tenant) for inboxes whose names match our scheme
        async with self._uow as uow:
            tenants = await uow.tenants.list_all()
            tenants_by_id = {t.id: t for t in tenants}
            inbox_to_party: dict[int, tuple[User, Tenant]] = {}
            for ib in inboxes:
                user_uuid = _user_uuid_from_inbox_name(ib.get("name", ""))
                if user_uuid is None:
                    continue
                # Find which tenant owns this user
                for t in tenants:
                    u = await uow.users.get_by_id(t.id, user_uuid)
                    if u is not None:
                        inbox_to_party[int(ib["id"])] = (u, tenants_by_id[t.id])
                        break

        convs = await self._messaging.list_conversations_for_contact(contact_id)
        out: list[dict] = []
        for c in convs:
            ibx = c.get("inbox_id")
            party = inbox_to_party.get(int(ibx)) if ibx is not None else None
            seller = party[0] if party else None
            tenant = party[1] if party else None
            out.append(self._enrich_thread(c, seller, tenant))
        return out

    async def post_message_as_external(
        self, identity: ExternalIdentity, conversation_id: int, content: str
    ) -> dict:
        contact_id = await self._ensure_chatwoot_contact(
            tenant_slug=identity.tenant_slug,
            external_sub=identity.external_sub,
            name=identity.name,
            email=identity.email,
        )
        owned = await self._messaging.list_conversations_for_contact(contact_id)
        if not any(int(c["id"]) == int(conversation_id) for c in owned):
            raise NotFoundError("Conversation not found")
        return await self._messaging.send_message(
            conversation_id=conversation_id,
            content=content,
            message_type="incoming",
        )

    # ------- seller (staff) inbox view -------
    async def list_inbox_threads_for_user(
        self, tenant_id: UUID, user_id: UUID
    ) -> list[dict]:
        async with self._uow as uow:
            tenant = await uow.tenants.get_by_id(tenant_id)
            user = await uow.users.get_by_id(tenant_id, user_id) if tenant else None
        if tenant is None or user is None:
            raise NotFoundError("User not found")
        inbox_id = await self._ensure_user_inbox(user)
        convs = await self._messaging.list_conversations_for_inbox(inbox_id)
        return [self._enrich_thread(c, user, tenant) for c in convs]

    async def post_staff_message(
        self, tenant_id: UUID, user_id: UUID, conversation_id: int, content: str
    ) -> dict:
        async with self._uow as uow:
            tenant = await uow.tenants.get_by_id(tenant_id)
            user = await uow.users.get_by_id(tenant_id, user_id) if tenant else None
        if tenant is None or user is None:
            raise NotFoundError("User not found")
        inbox_id = await self._ensure_user_inbox(user)
        convs = await self._messaging.list_conversations_for_inbox(inbox_id)
        if not any(int(c["id"]) == int(conversation_id) for c in convs):
            raise NotFoundError("Conversation not in your inbox")
        return await self._messaging.send_message(
            conversation_id=conversation_id,
            content=content,
            message_type="outgoing",
        )

    async def list_thread_messages(self, conversation_id: int) -> list[dict]:
        return await self._messaging.list_messages(conversation_id)

    # ------- enrichment -------
    @staticmethod
    def _enrich_thread(
        c: dict, seller: User | None, tenant: Tenant | None
    ) -> dict:
        meta = c.get("meta", {}) if isinstance(c.get("meta", {}), dict) else {}
        sender = meta.get("sender", {}) if isinstance(meta.get("sender", {}), dict) else {}
        last = (
            c.get("last_non_activity_message")
            or (c.get("messages") or [None])[-1]
        )
        return {
            "id": int(c["id"]) if c.get("id") is not None else None,
            "inbox_id": c.get("inbox_id"),
            "status": c.get("status"),
            "tenant": {
                "tenant_id": str(tenant.id) if tenant else None,
                "slug": tenant.slug if tenant else None,
                "name": tenant.name if tenant else None,
            } if tenant else None,
            "seller": {
                "user_id": str(seller.id) if seller else None,
                "email": seller.email if seller else None,
                "full_name": seller.full_name if seller else None,
                "role": seller.role.value if seller else None,
            } if seller else None,
            "contact": {
                "id": sender.get("id"),
                "name": sender.get("name"),
                "email": sender.get("email"),
                "identifier": sender.get("identifier"),
            },
            "last_message": last,
            "unread_count": c.get("unread_count", 0),
        }
