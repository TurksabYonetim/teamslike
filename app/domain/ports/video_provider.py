from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VideoRoom:
    room_name: str
    join_url: str
    moderator_token: str | None = None
    guest_token: str | None = None


class VideoProviderPort(ABC):
    @abstractmethod
    async def create_room(
        self,
        room_name: str,
        moderator_email: str,
        moderator_name: str,
        tenant_slug: str,
    ) -> VideoRoom: ...

    @abstractmethod
    async def issue_guest_token(
        self, room_name: str, guest_name: str, tenant_slug: str
    ) -> str: ...
