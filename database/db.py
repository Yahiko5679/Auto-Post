"""
Database Layer — MongoDB via motor (async).
Collections: users, templates, posts, banned
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME, FREE_POSTS_PER_DAY, PREMIUM_POSTS_PER_DAY

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None


def get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client[DB_NAME]


# ── User Operations ────────────────────────────────────────────────────────────

async def get_user(user_id: int) -> Optional[Dict]:
    return await get_db().users.find_one({"user_id": user_id})


async def upsert_user(user_id: int, username: str, full_name: str):
    now = datetime.utcnow()
    await get_db().users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username": username,
                "full_name": full_name,
                "last_seen": now,
            },
            "$setOnInsert": {
                "user_id": user_id,
                "joined": now,
                "is_premium": False,
                "is_banned": False,
                "post_count": 0,
                "daily_posts": {},
                "settings": {
                    "watermark": "",
                    "channel_id": None,
                    "active_template": "default",
                    "auto_post": False,
                    "quality": "480p | 720p | 1080p",
                    "audio": "Hindi | English",
                },
            },
        },
        upsert=True,
    )


async def is_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user.get("is_banned"))


async def ban_user(user_id: int):
    await get_db().users.update_one(
        {"user_id": user_id}, {"$set": {"is_banned": True}}
    )


async def unban_user(user_id: int):
    await get_db().users.update_one(
        {"user_id": user_id}, {"$set": {"is_banned": False}}
    )


async def set_premium(user_id: int, value: bool):
    await get_db().users.update_one(
        {"user_id": user_id}, {"$set": {"is_premium": value}}
    )


async def get_user_settings(user_id: int) -> Dict:
    user = await get_user(user_id)
    if user:
        return user.get("settings", {})
    return {}


async def update_user_settings(user_id: int, settings: Dict):
    await get_db().users.update_one(
        {"user_id": user_id},
        {"$set": {f"settings.{k}": v for k, v in settings.items()}},
    )


async def can_post_today(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return True
    today = str(date.today())
    limit = PREMIUM_POSTS_PER_DAY if user.get("is_premium") else FREE_POSTS_PER_DAY
    daily = user.get("daily_posts", {})
    return daily.get(today, 0) < limit


async def increment_post_count(user_id: int):
    today = str(date.today())
    await get_db().users.update_one(
        {"user_id": user_id},
        {
            "$inc": {
                "post_count": 1,
                f"daily_posts.{today}": 1,
            }
        },
    )


async def get_all_user_ids() -> List[int]:
    cursor = get_db().users.find({"is_banned": False}, {"user_id": 1})
    return [doc["user_id"] async for doc in cursor]


async def total_users() -> int:
    return await get_db().users.count_documents({})


async def total_posts() -> int:
    result = await get_db().users.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$post_count"}}}
    ]).to_list(1)
    return result[0]["total"] if result else 0


# ── Template Operations ────────────────────────────────────────────────────────

async def save_template(user_id: int, name: str, body: str, category: str = "all"):
    await get_db().templates.update_one(
        {"user_id": user_id, "name": name},
        {"$set": {"body": body, "category": category, "updated": datetime.utcnow()}},
        upsert=True,
    )


async def get_template(user_id: int, name: str) -> Optional[Dict]:
    return await get_db().templates.find_one({"user_id": user_id, "name": name})


async def list_user_templates(user_id: int) -> List[Dict]:
    cursor = get_db().templates.find({"user_id": user_id})
    return await cursor.to_list(50)


async def delete_template(user_id: int, name: str):
    await get_db().templates.delete_one({"user_id": user_id, "name": name})


async def get_active_template(user_id: int, category: str) -> Optional[str]:
    """Return template body for the user's active template, or None to use default."""
    settings = await get_user_settings(user_id)
    active_name = settings.get("active_template", "default")
    if active_name == "default":
        return None
    tpl = await get_template(user_id, active_name)
    return tpl["body"] if tpl else None
