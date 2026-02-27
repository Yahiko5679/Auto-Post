"""
FSM State Manager — Redis-backed per-user state storage.
Falls back to in-memory dict if Redis is unavailable.
"""

import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# In-memory fallback store
_memory_store: Dict[int, Dict] = {}


class StateManager:
    def __init__(self):
        self._redis = None
        self._try_connect()

    def _try_connect(self):
        try:
            import redis.asyncio as aioredis
            from config import REDIS_URL
            self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        except Exception:
            logger.warning("Redis unavailable — using in-memory FSM store.")

    async def set_state(self, user_id: int, data: Dict[str, Any], ttl: int = 600):
        """Store state for user. TTL in seconds (default 10 min)."""
        key = f"fsm:{user_id}"
        payload = json.dumps(data)
        if self._redis:
            try:
                await self._redis.set(key, payload, ex=ttl)
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        _memory_store[user_id] = data

    async def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve state for user."""
        key = f"fsm:{user_id}"
        if self._redis:
            try:
                raw = await self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        return _memory_store.get(user_id)

    async def update_state(self, user_id: int, updates: Dict[str, Any]):
        """Merge updates into existing state."""
        current = await self.get_state(user_id) or {}
        current.update(updates)
        await self.set_state(user_id, current)

    async def clear_state(self, user_id: int):
        """Delete state for user."""
        key = f"fsm:{user_id}"
        if self._redis:
            try:
                await self._redis.delete(key)
                return
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
        _memory_store.pop(user_id, None)
