from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt


class JWTError_(Exception):
    pass


class AppJWT:
    def __init__(self, secret: str, algorithm: str, access_minutes: int, refresh_days: int):
        self._secret = secret
        self._algo = algorithm
        self._access_minutes = access_minutes
        self._refresh_days = refresh_days

    def create_access_token(
        self, *, user_id: UUID, tenant_id: UUID, role: str, email: str
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "role": role,
            "email": email,
            "kind": "staff",
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._access_minutes)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algo)

    def create_customer_access_token(
        self, *, customer_id: UUID, email: str
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(customer_id),
            "email": email,
            "kind": "customer",
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._access_minutes)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algo)

    def create_customer_refresh_token(self, *, customer_id: UUID) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(customer_id),
            "kind": "customer",
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=self._refresh_days)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algo)

    def create_refresh_token(self, *, user_id: UUID, tenant_id: UUID) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=self._refresh_days)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algo)

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algo])
        except JWTError as e:
            raise JWTError_(str(e)) from e
