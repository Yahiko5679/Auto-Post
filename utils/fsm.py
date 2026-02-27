"""
FSM State Manager — Redis-backed with in-memory fallback.
Singleton: from utils.fsm import fsm
"""
import json
import logging
from typing import Optional, Dict
import config as cfg

logger = logging.getLogger(__name__)

_store: Dict[int, Dict] = {}   # in-memory fallback


class StateManager:
    def __init__(self):
        self._redis = None
        self._connect()

    def _connect(self):
        try:
            if cfg.REDIS_URL:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(cfg.REDIS_URL, decode_responses=True)
                logger.info("FSM: Redis connected.")
        except Exception:
            logger.info("FSM: Redis unavailable — using in-memory store.")

    async def set(self, user_id: int, data: Dict, ttl: int = 600):
        if self._redis:
            try:
                await self._redis.set(f"fsm:{user_id}", json.dumps(data), ex=ttl)
                return
            except Exception as e:
                logger.error(f"FSM Redis set: {e}")
        _store[user_id] = data

    async def get(self, user_id: int) -> Optional[Dict]:
        if self._redis:
            try:
                raw = await self._redis.get(f"fsm:{user_id}")
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.error(f"FSM Redis get: {e}")
        return _store.get(user_id)

    async def update(self, user_id: int, updates: Dict):
        current = await self.get(user_id) or {}
        current.update(updates)
        await self.set(user_id, current)

    async def clear(self, user_id: int):
        if self._redis:
            try:
                await self._redis.delete(f"fsm:{user_id}")
                return
            except Exception as e:
                logger.error(f"FSM Redis del: {e}")
        _store.pop(user_id, None)


fsm = StateManager()
