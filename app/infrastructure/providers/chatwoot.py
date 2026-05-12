import httpx

from app.domain.exceptions import ProviderError
from app.domain.ports.messaging_provider import (
    MessagingContact,
    MessagingConversation,
    MessagingProviderPort,
)


class ChatwootProvider(MessagingProviderPort):
    def __init__(self, *, base_url: str, user_api_token: str, account_id: int):
        self._base_url = base_url.rstrip("/")
        self._token = user_api_token
        self._account_id = account_id

    def _account_path(self, suffix: str) -> str:
        return f"{self._base_url}/api/v1/accounts/{self._account_id}{suffix}"

    @property
    def _headers(self) -> dict[str, str]:
        return {"api_access_token": self._token, "Content-Type": "application/json"}

    async def upsert_contact(
        self, name: str, email: str | None, identifier: str | None = None
    ) -> MessagingContact:
        async with httpx.AsyncClient(timeout=15) as client:
            payload: dict = {"name": name}
            if email:
                payload["email"] = email
            if identifier:
                payload["identifier"] = identifier
            r = await client.post(
                self._account_path("/contacts"), json=payload, headers=self._headers
            )
            if r.status_code == 422 and identifier:
                rs = await client.get(
                    self._account_path("/contacts/search"),
                    params={"q": identifier},
                    headers=self._headers,
                )
                rs.raise_for_status()
                items = rs.json().get("payload", [])
                if items:
                    c = items[0]
                    return MessagingContact(
                        id=c["id"],
                        name=c.get("name", ""),
                        email=c.get("email"),
                        identifier=c.get("identifier"),
                    )
            if r.status_code >= 400:
                raise ProviderError(f"Chatwoot upsert_contact failed: {r.status_code} {r.text}")
            data = r.json().get("payload", {}).get("contact") or r.json().get("payload", {})
            return MessagingContact(
                id=data["id"],
                name=data.get("name", name),
                email=data.get("email"),
                identifier=data.get("identifier"),
            )

    async def create_conversation(
        self, contact_id: int, inbox_id: int, source_id: str | None = None
    ) -> MessagingConversation:
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {
                "source_id": source_id or f"teamslike-{contact_id}",
                "inbox_id": inbox_id,
                "contact_id": contact_id,
                "status": "open",
            }
            r = await client.post(
                self._account_path("/conversations"),
                json=payload,
                headers=self._headers,
            )
            if r.status_code >= 400:
                raise ProviderError(
                    f"Chatwoot create_conversation failed: {r.status_code} {r.text}"
                )
            data = r.json()
            return MessagingConversation(
                id=data["id"],
                contact_id=contact_id,
                inbox_id=inbox_id,
                status=data.get("status", "open"),
            )

    async def send_message(
        self, conversation_id: int, content: str, message_type: str = "outgoing"
    ) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {"content": content, "message_type": message_type}
            r = await client.post(
                self._account_path(f"/conversations/{conversation_id}/messages"),
                json=payload,
                headers=self._headers,
            )
            if r.status_code >= 400:
                raise ProviderError(f"Chatwoot send_message failed: {r.status_code} {r.text}")
            return r.json()

    async def list_inboxes(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(self._account_path("/inboxes"), headers=self._headers)
            if r.status_code >= 400:
                raise ProviderError(f"Chatwoot list_inboxes failed: {r.status_code} {r.text}")
            return r.json().get("payload", [])

    async def ensure_default_inbox(self, name: str) -> dict:
        existing = await self.list_inboxes()
        for ib in existing:
            if ib.get("name") == name:
                return ib
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {"name": name, "channel": {"type": "api", "webhook_url": ""}}
            r = await client.post(
                self._account_path("/inboxes"), json=payload, headers=self._headers
            )
            if r.status_code >= 400:
                raise ProviderError(
                    f"Chatwoot create_inbox failed: {r.status_code} {r.text}"
                )
            return r.json()

    async def list_conversations_for_contact(self, contact_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                self._account_path(f"/contacts/{contact_id}/conversations"),
                headers=self._headers,
            )
            if r.status_code >= 400:
                raise ProviderError(
                    f"Chatwoot list_conversations_for_contact failed: {r.status_code} {r.text}"
                )
            data = r.json()
            payload = data.get("payload", data)
            # Chatwoot returns either [{...}] or {"data":{"payload":[{...}]}}
            if isinstance(payload, dict):
                payload = payload.get("payload") or payload.get("data") or []
            return payload or []

    async def list_conversations_for_inbox(self, inbox_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                self._account_path("/conversations"),
                params={"inbox_id": inbox_id, "status": "all"},
                headers=self._headers,
            )
            if r.status_code >= 400:
                raise ProviderError(
                    f"Chatwoot list_conversations_for_inbox failed: {r.status_code} {r.text}"
                )
            d = r.json().get("data", {})
            return d.get("payload", []) or []

    async def list_messages(self, conversation_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                self._account_path(f"/conversations/{conversation_id}/messages"),
                headers=self._headers,
            )
            if r.status_code >= 400:
                raise ProviderError(
                    f"Chatwoot list_messages failed: {r.status_code} {r.text}"
                )
            return r.json().get("payload", []) or []
