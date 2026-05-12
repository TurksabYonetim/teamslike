from datetime import datetime, timedelta, timezone

from jose import jwt

from app.domain.ports.video_provider import VideoProviderPort, VideoRoom


class JitsiProvider(VideoProviderPort):
    def __init__(
        self,
        *,
        public_url: str,
        app_id: str,
        app_secret: str,
        algorithm: str,
        token_ttl_minutes: int,
        domain: str,
    ):
        self._public_url = public_url.rstrip("/")
        self._app_id = app_id
        self._app_secret = app_secret
        self._algo = algorithm
        self._ttl = token_ttl_minutes
        self._domain = domain

    def _build_token(
        self,
        *,
        room: str,
        name: str,
        email: str,
        is_moderator: bool,
        tenant_slug: str,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "aud": self._app_id,
            "iss": self._app_id,
            "sub": self._domain,
            "room": room,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._ttl)).timestamp()),
            "context": {
                "user": {
                    "id": f"{tenant_slug}:{email or name}",
                    "name": name,
                    "email": email,
                    "moderator": is_moderator,
                },
                "features": {
                    "livestreaming": is_moderator,
                    "recording": is_moderator,
                    "transcription": True,
                    "outbound-call": False,
                },
                "group": tenant_slug,
            },
        }
        return jwt.encode(payload, self._app_secret, algorithm=self._algo)

    async def create_room(
        self,
        room_name: str,
        moderator_email: str,
        moderator_name: str,
        tenant_slug: str,
    ) -> VideoRoom:
        token = self._build_token(
            room=room_name,
            name=moderator_name,
            email=moderator_email,
            is_moderator=True,
            tenant_slug=tenant_slug,
        )
        join_url = f"{self._public_url}/{room_name}?jwt={token}"
        return VideoRoom(
            room_name=room_name, join_url=join_url, moderator_token=token, guest_token=None
        )

    async def issue_guest_token(
        self, room_name: str, guest_name: str, tenant_slug: str
    ) -> str:
        return self._build_token(
            room=room_name,
            name=guest_name,
            email="",
            is_moderator=False,
            tenant_slug=tenant_slug,
        )
