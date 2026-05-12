from redis.asyncio import Redis

from app.domain.ports.cache import CachePort


class RedisCache(CachePort):
    def __init__(self, redis: Redis, key_prefix: str = "teamslike"):
        self._r = redis
        self._prefix = key_prefix

    def _k(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> str | None:
        v = await self._r.get(self._k(key))
        return v.decode() if isinstance(v, bytes) else v

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        await self._r.set(self._k(key), value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._r.delete(self._k(key))

    async def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        full = self._k(key)
        n = await self._r.incr(full)
        if n == 1 and ttl_seconds:
            await self._r.expire(full, ttl_seconds)
        return n
