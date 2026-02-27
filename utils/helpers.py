"""
Handler Utilities — decorators, helpers, shared logic.
"""

import functools
import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from database.db import CosmicBotz
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def require_not_banned(func):
    """Decorator: block banned users."""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
        if await CosmicBotz.is_banned(user.id):
            await update.effective_message.reply_text(
                "🚫 You have been banned from using this bot."
            )
            return
        return await func(self, update, context, *args, **kwargs)
    return wrapper


def require_admin(func):
    """Decorator: only allow admins."""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in ADMIN_IDS:
            await update.effective_message.reply_text("⛔ Admin only.")
            return
        return await func(self, update, context, *args, **kwargs)
    return wrapper


def track_user(func):
    """Decorator: upsert user in DB on every interaction."""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user:
            await CosmicBotz.upsert_user(user.id, user.username or "", user.full_name or "")
        return await func(self, update, context, *args, **kwargs)
    return wrapper


def check_daily_limit(func):
    """Decorator: enforce daily post limit."""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user and not await CosmicBotz.can_post_today(user.id):
            await update.effective_message.reply_text(
                "⚠️ You've reached your daily post limit.\n"
                "Upgrade to ⭐ Premium for unlimited posts!"
            )
            return
        return await func(self, update, context, *args, **kwargs)
    return wrapper


async def safe_edit(message, text: str, reply_markup=None, parse_mode=ParseMode.HTML):
    """Edit a message safely, ignoring 'message not modified' errors."""
    try:
        kwargs = {"text": text, "parse_mode": parse_mode}
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        await message.edit_text(**kwargs)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"safe_edit failed: {e}")


async def safe_answer(query, text="", alert=False):
    """Answer callback query safely."""
    try:
        await query.answer(text, show_alert=alert)
    except Exception:
        pass


def extract_query(message_text: str, command: str) -> str:
    """Extract search query from command text, e.g. '/movie dr strange' → 'dr strange'."""
    parts = message_text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


async def send_or_reply(update: Update, text: str, reply_markup=None, parse_mode=ParseMode.HTML):
    """Send message, preferring reply."""
    msg = update.effective_message
    kwargs = {"text": text, "parse_mode": parse_mode}
    if reply_markup:
        kwargs["reply_markup"] = reply_markup
    return await msg.reply_text(**kwargs)


async def post_to_channel(context, channel_id: str, photo_bytes: bytes, caption: str):
    """Send a photo post to a Telegram channel."""
    import io
    try:
        await context.bot.send_photo(
            chat_id=channel_id,
            photo=io.BytesIO(photo_bytes),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        return True
    except Exception as e:
        logger.error(f"Channel post failed: {e}")
        return False
