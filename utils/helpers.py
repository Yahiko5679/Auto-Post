"""
Shared helpers — decorators + keyboard builders.
"""
import io
import functools
import logging
from typing import List, Dict

from pyrofork import Client
from pyrofork.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from database.db import CosmicBotz
import config as cfg

logger = logging.getLogger(__name__)


# ── Decorators ────────────────────────────────────────────────────────────────

def track_user(func):
    """Upsert user on every interaction."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        u = message.from_user
        if u:
            await CosmicBotz.upsert_user(u.id, u.username or "", u.full_name or "")
        return await func(client, message, *args, **kwargs)
    return wrapper


def banned_check(func):
    """Block banned users silently."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        u = message.from_user
        if u and await CosmicBotz.is_banned(u.id):
            await message.reply("🚫 You are banned from using this bot.")
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def admin_only(func):
    """Restrict handler to admins."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        if not message.from_user or message.from_user.id not in cfg.ADMIN_IDS:
            await message.reply("⛔ Admin only.")
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def daily_limit_check(func):
    """Enforce daily post limit before running handler."""
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        u = message.from_user
        if u and not await CosmicBotz.can_post_today(u.id):
            await message.reply(
                "⚠️ Daily post limit reached!\n"
                "Upgrade to ⭐ **Premium** for unlimited posts."
            )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


# ── Keyboard builders ─────────────────────────────────────────────────────────

def search_kb(results: List[Dict], prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            f"{r['title']} ({r.get('year', '?')})",
            callback_data=f"{prefix}_select_{r['id']}",
        )]
        for r in results
    ]
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"{prefix}_cancel")])
    return InlineKeyboardMarkup(rows)


def thumbnail_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Skip — Use Auto Poster", callback_data=f"{prefix}_thumb_skip")],
        [InlineKeyboardButton("❌ Cancel",                callback_data=f"{prefix}_cancel")],
    ])


def preview_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Post to Channel", callback_data=f"{prefix}_post_channel"),
            InlineKeyboardButton("📋 Copy Caption",    callback_data=f"{prefix}_post_copy"),
        ],
        [
            InlineKeyboardButton("🔄 Change Template", callback_data=f"{prefix}_change_tpl"),
            InlineKeyboardButton("🖼 Redo Thumbnail",  callback_data=f"{prefix}_redo_thumb"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"{prefix}_cancel")],
    ])


def template_kb(templates: List[Dict], prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("⭐ Default Template", callback_data=f"{prefix}_tpl_default")]]
    for t in templates:
        rows.append([InlineKeyboardButton(
            f"📄 {t['name']}",
            callback_data=f"{prefix}_tpl_{t['name']}",
        )])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"{prefix}_back_preview")])
    return InlineKeyboardMarkup(rows)


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖋 Watermark",    callback_data="cfg_watermark"),
            InlineKeyboardButton("📺 Channel",      callback_data="cfg_channel"),
        ],
        [
            InlineKeyboardButton("🎞 Quality",      callback_data="cfg_quality"),
            InlineKeyboardButton("🔊 Audio",        callback_data="cfg_audio"),
        ],
        [
            InlineKeyboardButton("📋 Templates",    callback_data="cfg_templates"),
            InlineKeyboardButton("📊 My Stats",     callback_data="cfg_stats"),
        ],
        [InlineKeyboardButton("✖ Close", callback_data="cfg_close")],
    ])


def quality_kb() -> InlineKeyboardMarkup:
    opts = [
        "480p | 720p | 1080p",
        "720p | 1080p | 4K",
        "480p | 720p",
        "1080p | 4K",
    ]
    rows = [[InlineKeyboardButton(o, callback_data=f"cfg_setquality|{o}")] for o in opts]
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="cfg_back")])
    return InlineKeyboardMarkup(rows)


def audio_kb() -> InlineKeyboardMarkup:
    opts = [
        "Hindi | English",
        "Hindi | English | Tamil | Telugu",
        "English Only",
        "Dual Audio",
    ]
    rows = [[InlineKeyboardButton(o, callback_data=f"cfg_setaudio|{o}")] for o in opts]
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="cfg_back")])
    return InlineKeyboardMarkup(rows)


def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats",        callback_data="adm_stats"),
            InlineKeyboardButton("📢 Broadcast",    callback_data="adm_broadcast"),
        ],
        [
            InlineKeyboardButton("⭐ Add Premium",  callback_data="adm_addprem"),
            InlineKeyboardButton("⛔ Ban User",     callback_data="adm_ban"),
        ],
        [InlineKeyboardButton("✖ Close", callback_data="adm_close")],
    ])


# ── Misc ──────────────────────────────────────────────────────────────────────

async def post_to_channel(
    client: Client, channel_id: str, photo: bytes, caption: str
) -> bool:
    try:
        await client.send_photo(
            chat_id=channel_id,
            photo=io.BytesIO(photo),
            caption=caption,
        )
        return True
    except Exception as e:
        logger.error(f"Channel post failed: {e}")
        return False


def extract_query(text: str) -> str:
    """/movie dr strange  →  'dr strange'"""
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
