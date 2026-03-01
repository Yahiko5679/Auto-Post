"""
Database — MongoDB via motor (async).

Usage anywhere:
    from database.db import CosmicBotz
    await CosmicBotz.get_user(user_id)
"""
import logging
from datetime import datetime, date
from typing import Optional, Dict, List
from motor.motor_asyncio import AsyncIOMotorClient
import config as cfg

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None

    def _db(self):
        if self._client is None:
            self._client = AsyncIOMotorClient(cfg.MONGO_URI)
        return self._client["CosmicBotz"]

    # ── Users ─────────────────────────────────────────────────────────────────

    async def get_user(self, user_id: int) -> Optional[Dict]:
        return await self._db().users.find_one({"user_id": user_id})

    async def upsert_user(self, user_id: int, username: str, full_name: str):
        now = datetime.utcnow()
        await self._db().users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username":  username,
                    "full_name": full_name,
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "user_id":    user_id,
                    "joined":     now,
                    "is_premium": False,
                    "is_banned":  False,
                    "post_count": 0,
                    "daily_posts": {},
                    "settings": {
                        "watermark":       "",
                        "channel_id":      None,
                        "active_template": "default",
                        "quality":         cfg.DEFAULT_QUALITY,
                        "audio":           cfg.DEFAULT_AUDIO,
                    },
                },
            },
            upsert=True,
        )

    async def is_banned(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return bool(user and user.get("is_banned"))

    async def ban_user(self, user_id: int):
        await self._db().users.update_one(
            {"user_id": user_id}, {"$set": {"is_banned": True}}
        )

    async def unban_user(self, user_id: int):
        await self._db().users.update_one(
            {"user_id": user_id}, {"$set": {"is_banned": False}}
        )

    async def set_premium(self, user_id: int, value: bool):
        await self._db().users.update_one(
            {"user_id": user_id}, {"$set": {"is_premium": value}}
        )

    async def get_user_settings(self, user_id: int) -> Dict:
        user = await self.get_user(user_id)
        return user.get("settings", {}) if user else {}

    async def update_user_settings(self, user_id: int, settings: Dict):
        await self._db().users.update_one(
            {"user_id": user_id},
            {"$set": {f"settings.{k}": v for k, v in settings.items()}},
        )

    async def can_post_today(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        if not user:
            return True
        today = str(date.today())
        limit = (
            cfg.PREMIUM_POSTS_PER_DAY
            if user.get("is_premium")
            else cfg.FREE_POSTS_PER_DAY
        )
        return user.get("daily_posts", {}).get(today, 0) < limit

    async def increment_post_count(self, user_id: int):
        today = str(date.today())
        await self._db().users.update_one(
            {"user_id": user_id},
            {"$inc": {"post_count": 1, f"daily_posts.{today}": 1}},
        )

    async def get_all_user_ids(self) -> List[int]:
        cursor = self._db().users.find({"is_banned": False}, {"user_id": 1})
        return [doc["user_id"] async for doc in cursor]

    async def total_users(self) -> int:
        return await self._db().users.count_documents({})

    async def total_posts(self) -> int:
        result = await self._db().users.aggregate(
            [{"$group": {"_id": None, "total": {"$sum": "$post_count"}}}]
        ).to_list(1)
        return result[0]["total"] if result else 0

    # ── Templates ─────────────────────────────────────────────────────────────

    async def save_template(self, user_id: int, name: str, body: str):
        await self._db().templates.update_one(
            {"user_id": user_id, "name": name},
            {"$set": {"body": body, "updated": datetime.utcnow()}},
            upsert=True,
        )

    async def get_template(self, user_id: int, name: str) -> Optional[Dict]:
        return await self._db().templates.find_one({"user_id": user_id, "name": name})

    async def list_user_templates(self, user_id: int) -> List[Dict]:
        return await self._db().templates.find({"user_id": user_id}).to_list(50)

    async def delete_template(self, user_id: int, name: str):
        await self._db().templates.delete_one({"user_id": user_id, "name": name})

    async def get_active_template(self, user_id: int) -> Optional[str]:
        settings = await self.get_user_settings(user_id)
        name = settings.get("active_template", "default")
        if name == "default":
            return None
        tpl = await self.get_template(user_id, name)
        return tpl["body"] if tpl else None


# ── Singleton ─────────────────────────────────────────────────────────────────
CosmicBotz = Database()
