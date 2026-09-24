import json
from typing import Awaitable, Callable

from redis.asyncio import Redis


class EventBus:
    def __init__(self, redis_url: str | None) -> None:
        self.redis_url = redis_url
        self.redis: Redis | None = None

    async def connect(self) -> None:
        if self.redis_url:
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()

    async def close(self) -> None:
        if self.redis: await self.redis.aclose()

    async def publish(self, stream: str, payload: dict) -> str | None:
        if not self.redis: return None
        return await self.redis.xadd(stream, {"payload": json.dumps(payload, ensure_ascii=False)}, maxlen=10_000)

    async def queue_audio(self, payload: dict) -> str | None:
        return await self.publish("scribe:audio", payload)
