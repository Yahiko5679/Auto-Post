"""
Settings Handler — watermark, channel, quality, audio, etc.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import get_user_settings, update_user_settings, get_user
from fsm.state_manager import StateManager
from utils.keyboards import settings_main_kb, quality_kb, audio_kb
from utils.helpers import safe_edit, safe_answer, track_user, require_not_banned

logger = logging.getLogger(__name__)


class SettingsHandler:
    def __init__(self):
        self.sm = StateManager()

    @require_not_banned
    @track_user
    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        settings = await get_user_settings(user_id)
        user = await get_user(user_id)
        premium = "⭐ Premium" if user and user.get("is_premium") else "Free"

        text = (
            f"⚙️ <b>Settings</b> [{premium}]\n\n"
            f"🖋 Watermark:  <code>{settings.get('watermark') or 'Not set'}</code>\n"
            f"📺 Channel:    <code>{settings.get('channel_id') or 'Not set'}</code>\n"
            f"🎞 Quality:    <code>{settings.get('quality', '480p | 720p | 1080p')}</code>\n"
            f"🔊 Audio:      <code>{settings.get('audio', 'Hindi | English')}</code>\n"
            f"📋 Template:   <code>{settings.get('active_template', 'default')}</code>\n"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                         reply_markup=settings_main_kb())

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await safe_answer(query)
        data = query.data
        user_id = update.effective_user.id

        if data == "settings_watermark":
            await self.sm.set_state(user_id, {"awaiting_watermark": True})
            await safe_edit(
                query.message,
                "🖋 <b>Set Watermark</b>\n\n"
                "Send me the watermark text to display on thumbnails.\n"
                "Example: <code>@YourChannel</code>\n\n"
                "Send <code>clear</code> to remove watermark.",
            )

        elif data == "settings_channel":
            await self.sm.set_state(user_id, {"awaiting_channel": True})
            await safe_edit(
                query.message,
                "📺 <b>Set Channel</b>\n\n"
                "Send me your channel username or ID.\n"
                "Example: <code>@MyAnimeChannel</code>\n\n"
                "⚠️ Make sure to add this bot as an <b>admin</b> in your channel first!",
            )

        elif data == "settings_quality":
            await safe_edit(query.message, "🎞 <b>Select Quality:</b>",
                            reply_markup=quality_kb())

        elif data == "settings_audio":
            await safe_edit(query.message, "🔊 <b>Select Audio:</b>",
                            reply_markup=audio_kb())

        elif data.startswith("settings_setquality_"):
            val = data[len("settings_setquality_"):]
            await update_user_settings(user_id, {"quality": val})
            await safe_answer(query, f"✅ Quality set to: {val}", alert=True)
            await safe_edit(query.message, "⚙️ Settings updated!", reply_markup=settings_main_kb())

        elif data.startswith("settings_setaudio_"):
            val = data[len("settings_setaudio_"):]
            await update_user_settings(user_id, {"audio": val})
            await safe_answer(query, f"✅ Audio set to: {val}", alert=True)
            await safe_edit(query.message, "⚙️ Settings updated!", reply_markup=settings_main_kb())

        elif data == "settings_templates":
            from handlers.template import TemplateHandler
            await TemplateHandler().list_templates(update, context)

        elif data == "settings_stats":
            user = await get_user(user_id)
            posts = user.get("post_count", 0) if user else 0
            premium = "⭐ Yes" if user and user.get("is_premium") else "No"
            await safe_edit(
                query.message,
                f"📊 <b>My Stats</b>\n\n"
                f"Total Posts: <b>{posts}</b>\n"
                f"Premium: <b>{premium}</b>\n",
                reply_markup=None,
            )

        elif data == "settings_back":
            await safe_edit(query.message, "⚙️ Settings", reply_markup=settings_main_kb())

        elif data == "settings_close":
            await query.message.delete()

    @require_not_banned
    async def set_watermark(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        await self.sm.set_state(user_id, {"awaiting_watermark": True})
        await update.message.reply_text(
            "🖋 Send your watermark text (e.g. <code>@YourChannel</code>):",
            parse_mode=ParseMode.HTML,
        )

    @require_not_banned
    async def set_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        await self.sm.set_state(user_id, {"awaiting_channel": True})
        await update.message.reply_text(
            "📺 Send your channel username or ID.\n"
            "Make sure bot is admin there first!",
        )

    async def handle_watermark_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        if text.lower() == "clear":
            await update_user_settings(user_id, {"watermark": ""})
            await update.message.reply_text("✅ Watermark cleared.")
        else:
            await update_user_settings(user_id, {"watermark": text})
            await update.message.reply_text(
                f"✅ Watermark set to: <code>{text}</code>", parse_mode=ParseMode.HTML
            )
        await self.sm.clear_state(user_id)

    async def handle_channel_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        # Validate
        if not (text.startswith("@") or text.lstrip("-").isdigit()):
            await update.message.reply_text(
                "❌ Invalid format. Use <code>@channel</code> or a numeric ID.",
                parse_mode=ParseMode.HTML,
            )
            return
        await update_user_settings(user_id, {"channel_id": text})
        await update.message.reply_text(
            f"✅ Channel set to <code>{text}</code>.\n"
            f"Ensure this bot is an admin there!",
            parse_mode=ParseMode.HTML,
        )
        await self.sm.clear_state(user_id)
