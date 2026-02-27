"""
Template Handler — Custom post format builder.
Users can create, view, edit, delete named templates.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import (
    save_template, get_template, list_user_templates,
    delete_template, update_user_settings, get_user_settings
)
from fsm.state_manager import StateManager
from formatter.engine import FormatEngine
from utils.helpers import safe_edit, safe_answer, track_user, require_not_banned

logger = logging.getLogger(__name__)


class TemplateHandler:
    def __init__(self):
        self.sm = StateManager()
        self.fmt = FormatEngine()

    @require_not_banned
    @track_user
    async def list_templates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        templates = await list_user_templates(user_id)
        settings = await get_user_settings(user_id)
        active = settings.get("active_template", "default")

        if not templates:
            text = (
                "📋 <b>My Templates</b>\n\n"
                "You have no custom templates yet.\n\n"
                "Use /setformat to create your first template!"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            return

        text = f"📋 <b>My Templates</b> (Active: <code>{active}</code>)\n\n"
        rows = []
        for t in templates:
            marker = "✅ " if t["name"] == active else "📄 "
            text += f"{marker}<b>{t['name']}</b> — {t.get('category','all')}\n"
            rows.append([
                InlineKeyboardButton(f"👁 {t['name']}", callback_data=f"tpl_view_{t['name']}"),
                InlineKeyboardButton("✅ Use",          callback_data=f"tpl_use_{t['name']}"),
                InlineKeyboardButton("🗑 Delete",       callback_data=f"tpl_del_{t['name']}"),
            ])
        rows.append([InlineKeyboardButton("➕ New Template", callback_data="tpl_new")])

        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows)
        )

    @require_not_banned
    async def my_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        settings = await get_user_settings(user_id)
        active_name = settings.get("active_template", "default")

        if active_name == "default":
            await update.message.reply_text(
                "📋 You're using the <b>Default Template</b>.\n"
                "Use /setformat to create a custom one!",
                parse_mode=ParseMode.HTML,
            )
            return

        tpl = await get_template(user_id, active_name)
        if not tpl:
            await update.message.reply_text("❌ Active template not found.")
            return

        await update.message.reply_text(
            f"📋 <b>Active Template: {active_name}</b>\n\n"
            f"<pre>{tpl['body']}</pre>",
            parse_mode=ParseMode.HTML,
        )

    @require_not_banned
    async def set_format_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the template creation wizard."""
        user_id = update.effective_user.id
        await self.sm.set_state(user_id, {"awaiting_template_name": True})

        tokens_help = (
            "<b>Available Tokens:</b>\n"
            "Movie:  <code>{title} {year} {rating} {genres} {overview} {quality} {audio}</code>\n"
            "TV:     <code>{title} {seasons} {episodes} {status} {genres}</code>\n"
            "Anime:  <code>{title} {episodes} {status} {type} {synopsis}</code>\n"
            "Manhwa: <code>{title} {chapters} {status} {type} {synopsis}</code>\n\n"
            "<code>{hashtags}</code> — auto-generated hashtags\n"
        )
        await update.message.reply_text(
            f"📝 <b>Template Builder</b>\n\n"
            f"Let's create a custom post template.\n\n"
            f"{tokens_help}"
            f"First, send me a <b>name</b> for this template:\n"
            f"(e.g. <code>mymoviestyle</code>)",
            parse_mode=ParseMode.HTML,
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input during template creation."""
        user_id = update.effective_user.id
        state = await self.sm.get_state(user_id)
        text = update.message.text.strip()

        if state.get("awaiting_template_name"):
            if len(text) > 32 or " " in text:
                await update.message.reply_text(
                    "❌ Name must be under 32 chars and no spaces. Try again:"
                )
                return
            await self.sm.update_state(user_id, {
                "awaiting_template_name": False,
                "awaiting_template_body": True,
                "template_name": text,
            })
            await update.message.reply_text(
                f"✅ Name set: <b>{text}</b>\n\n"
                f"Now send me the <b>template body</b>.\n"
                f"Use tokens like <code>{{title}}</code>, <code>{{rating}}</code>, etc.\n\n"
                f"Example:\n"
                f"<pre>🎬 {{title}} ({{year}})\n\n"
                f"⭐ Rating: {{rating}}\n"
                f"🎭 Genre: {{genres}}\n\n"
                f"{{overview}}</pre>",
                parse_mode=ParseMode.HTML,
            )

        elif state.get("awaiting_template_body"):
            name = state.get("template_name", "unnamed")
            if "{title}" not in text:
                await update.message.reply_text(
                    "⚠️ Template must contain at least <code>{title}</code>. Try again:",
                    parse_mode=ParseMode.HTML,
                )
                return

            await save_template(user_id, name, text)
            await update_user_settings(user_id, {"active_template": name})
            await self.sm.clear_state(user_id)

            await update.message.reply_text(
                f"✅ <b>Template '{name}' saved and activated!</b>\n\n"
                f"Your posts will now use this template.\n"
                f"Use /templates to manage all templates.",
                parse_mode=ParseMode.HTML,
            )

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await safe_answer(query)
        data = query.data
        user_id = update.effective_user.id

        if data == "tpl_new":
            await self.sm.set_state(user_id, {"awaiting_template_name": True})
            await safe_edit(
                query.message,
                "📝 Send me a <b>name</b> for the new template:",
            )

        elif data.startswith("tpl_view_"):
            name = data[9:]
            tpl = await get_template(user_id, name)
            if tpl:
                await safe_edit(
                    query.message,
                    f"📋 <b>Template: {name}</b>\n\n<pre>{tpl['body']}</pre>",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Activate", callback_data=f"tpl_use_{name}"),
                        InlineKeyboardButton("🔙 Back",    callback_data="tpl_back"),
                    ]])
                )

        elif data.startswith("tpl_use_"):
            name = data[8:]
            await update_user_settings(user_id, {"active_template": name})
            await safe_answer(query, f"✅ Template '{name}' activated!", alert=True)

        elif data.startswith("tpl_del_"):
            name = data[8:]
            await delete_template(user_id, name)
            settings = await get_user_settings(user_id)
            if settings.get("active_template") == name:
                await update_user_settings(user_id, {"active_template": "default"})
            await safe_answer(query, f"🗑 Template '{name}' deleted.", alert=True)
            # Refresh list
            await self.list_templates(update, context)

        elif data == "tpl_back":
            await self.list_templates(update, context)
