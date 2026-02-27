"""
Base Content Handler — shared search → preview → thumbnail → post flow.
All category handlers (movie, tvshow, anime, manhwa) inherit from this.
"""

import io
import logging
from typing import List, Dict, Optional
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from fsm.state_manager import StateManager
from formatter.engine import FormatEngine
from thumbnail.processor import build_thumbnail, process_custom_thumbnail
from database.db import (
    get_user_settings, get_active_template, increment_post_count
)
from utils.keyboards import (
    search_results_kb, thumbnail_kb, post_preview_kb, template_select_kb
)
from utils.helpers import (
    safe_edit, safe_answer, extract_query, send_or_reply,
    post_to_channel, require_not_banned, track_user
)

logger = logging.getLogger(__name__)


class BaseHandler:
    CATEGORY: str = ""          # override in subclass
    PREFIX: str = ""            # callback prefix, e.g. "movie"

    def __init__(self):
        self.sm = StateManager()
        self.fmt = FormatEngine()

    # ── Abstract methods (implement in subclass) ───────────────────────────────

    async def _fetch_search(self, query: str) -> List[Dict]:
        raise NotImplementedError

    async def _fetch_detail(self, item_id) -> Optional[Dict]:
        raise NotImplementedError

    # ── Main search command ────────────────────────────────────────────────────

    @require_not_banned
    @track_user
    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = extract_query(update.message.text, f"/{self.CATEGORY}")
        if not query:
            await update.message.reply_text(
                f"Usage: <code>/{self.CATEGORY} &lt;title&gt;</code>\n"
                f"Example: <code>/{self.CATEGORY} {self._example()}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        msg = await update.message.reply_text(f"🔍 Searching for <b>{query}</b>...", parse_mode=ParseMode.HTML)

        results = await self._fetch_search(query)
        if not results:
            await msg.edit_text("❌ No results found. Try a different title.")
            return

        await self.sm.set_state(update.effective_user.id, {
            "category": self.CATEGORY,
            "search_results": results,
        })

        await msg.edit_text(
            f"🔎 Found <b>{len(results)}</b> results for <b>{query}</b>.\nSelect one:",
            reply_markup=search_results_kb(results, self.CATEGORY),
            parse_mode=ParseMode.HTML,
        )

    # ── Callback router ────────────────────────────────────────────────────────

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await safe_answer(query)
        data = query.data
        p = self.PREFIX

        if data.startswith(f"{p}_select_"):
            await self._on_select(update, context, data)
        elif data.startswith(f"{p}_thumb_skip"):
            await self._on_thumb_skip(update, context)
        elif data.startswith(f"{p}_post_channel"):
            await self._on_post_channel(update, context)
        elif data.startswith(f"{p}_post_copy"):
            await self._on_post_copy(update, context)
        elif data.startswith(f"{p}_change_template"):
            await self._on_change_template(update, context)
        elif data.startswith(f"{p}_tpl_"):
            await self._on_template_selected(update, context, data)
        elif data.startswith(f"{p}_back_preview"):
            await self._show_preview(update, context)
        elif data.startswith(f"{p}_redo_thumb"):
            await self._on_redo_thumb(update, context)
        elif data.startswith(f"{p}_cancel"):
            await self._on_cancel(update, context)

    # ── Flow steps ─────────────────────────────────────────────────────────────

    async def _on_select(self, update: Update, context, data: str):
        item_id = int(data.split("_")[-1])
        msg = update.callback_query.message

        await safe_edit(msg, "⏳ Fetching details...")

        meta = await self._fetch_detail(item_id)
        if not meta:
            await safe_edit(msg, "❌ Failed to fetch details. Try again.")
            return

        user_id = update.effective_user.id
        await self.sm.update_state(user_id, {
            "meta": meta,
            "awaiting_thumbnail": True,
        })

        await safe_edit(
            msg,
            f"🖼 <b>Custom Thumbnail</b>\n\n"
            f"<b>{meta['title']}</b> details fetched!\n\n"
            f"📸 Send me a <b>custom thumbnail image</b> for this post,\n"
            f"or click <b>Skip</b> to use the auto-generated poster.",
            reply_markup=thumbnail_kb(self.CATEGORY),
        )

    async def _on_thumb_skip(self, update: Update, context):
        """Use auto-generated thumbnail."""
        user_id = update.effective_user.id
        await self.sm.update_state(user_id, {
            "awaiting_thumbnail": False,
            "custom_image": None,
        })
        await self._show_preview(update, context)

    async def handle_thumbnail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Called when user sends a photo in thumbnail step."""
        user_id = update.effective_user.id
        state = await self.sm.get_state(user_id)
        if not state or not state.get("awaiting_thumbnail"):
            return

        photo = update.message.photo[-1]  # largest size
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()

        await self.sm.update_state(user_id, {
            "awaiting_thumbnail": False,
            "custom_image": bytes(photo_bytes),
        })

        await update.message.reply_text("✅ Custom thumbnail received! Generating preview...")
        await self._show_preview_from_message(update, context)

    async def _show_preview(self, update: Update, context):
        """Edit existing message to show preview."""
        user_id = update.effective_user.id
        state = await self.sm.get_state(user_id)
        if not state:
            return

        msg = update.callback_query.message
        await safe_edit(msg, "⚙️ Building your post preview...")

        thumb_bytes, caption = await self._build_post(user_id, state)

        # Send photo with caption as new message
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=io.BytesIO(thumb_bytes),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=post_preview_kb(self.CATEGORY),
        )
        await msg.delete()

    async def _show_preview_from_message(self, update: Update, context):
        """Send preview as reply to message (not edit)."""
        user_id = update.effective_user.id
        state = await self.sm.get_state(user_id)
        if not state:
            return

        thumb_bytes, caption = await self._build_post(user_id, state)

        await update.message.reply_photo(
            photo=io.BytesIO(thumb_bytes),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=post_preview_kb(self.CATEGORY),
        )

    async def _build_post(self, user_id: int, state: Dict):
        """Build thumbnail bytes + caption from state."""
        meta = state.get("meta", {})
        custom_image = state.get("custom_image")

        settings = await get_user_settings(user_id)
        watermark = settings.get("watermark", "")
        template_body = await get_active_template(user_id, self.CATEGORY)

        # Caption
        caption = self.fmt.render(
            self.CATEGORY, meta,
            template=template_body,
            user_settings=settings,
        )

        # Thumbnail
        if custom_image:
            thumb_bytes = await process_custom_thumbnail(custom_image, watermark=watermark)
        else:
            thumb_bytes = await build_thumbnail(
                poster_url=meta.get("poster"),
                backdrop_url=meta.get("backdrop") or meta.get("banner"),
                watermark=watermark,
            )

        # Store in state for posting
        await self.sm.update_state(user_id, {
            "caption": caption,
            "thumb_bytes": thumb_bytes,
        })

        return thumb_bytes, caption

    async def _on_post_channel(self, update: Update, context):
        user_id = update.effective_user.id
        state = await self.sm.get_state(user_id)
        settings = await get_user_settings(user_id)
        channel_id = settings.get("channel_id")

        if not channel_id:
            await safe_answer(
                update.callback_query,
                "⚠️ No channel set! Use /settings → Set Channel first.",
                alert=True
            )
            return

        caption = state.get("caption", "")
        thumb = state.get("thumb_bytes", b"")

        success = await post_to_channel(context, channel_id, thumb, caption)
        if success:
            await increment_post_count(user_id)
            await safe_answer(update.callback_query, "✅ Posted to channel!", alert=True)
            await self.sm.clear_state(user_id)
        else:
            await safe_answer(
                update.callback_query,
                "❌ Failed to post. Make sure the bot is admin in your channel.",
                alert=True
            )

    async def _on_post_copy(self, update: Update, context):
        user_id = update.effective_user.id
        state = await self.sm.get_state(user_id)
        caption = state.get("caption", "")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📋 <b>Your Caption:</b>\n\n{caption}",
            parse_mode=ParseMode.HTML,
        )
        await safe_answer(update.callback_query, "Caption sent!")
        await increment_post_count(user_id)

    async def _on_change_template(self, update: Update, context):
        from database.db import list_user_templates
        user_id = update.effective_user.id
        templates = await list_user_templates(user_id)
        await safe_edit(
            update.callback_query.message,
            "📄 <b>Select a Template:</b>\n\nChoose a template to apply to this post:",
            reply_markup=template_select_kb(templates, self.CATEGORY),
        )

    async def _on_template_selected(self, update: Update, context, data: str):
        tpl_name = data.split(f"{self.PREFIX}_tpl_", 1)[1]
        user_id = update.effective_user.id

        if tpl_name == "default":
            await self.sm.update_state(user_id, {"active_template_override": None})
        else:
            from database.db import get_template
            tpl = await get_template(user_id, tpl_name)
            if tpl:
                await self.sm.update_state(user_id, {
                    "active_template_override": tpl["body"]
                })

        await self._show_preview(update, context)

    async def _on_redo_thumb(self, update: Update, context):
        user_id = update.effective_user.id
        await self.sm.update_state(user_id, {"awaiting_thumbnail": True})
        await safe_edit(
            update.callback_query.message,
            "📸 <b>Send a new thumbnail image</b>, or click Skip:",
            reply_markup=thumbnail_kb(self.CATEGORY),
        )

    async def _on_cancel(self, update: Update, context):
        user_id = update.effective_user.id
        await self.sm.clear_state(user_id)
        await safe_edit(update.callback_query.message, "✅ Cancelled.")

    def _example(self) -> str:
        examples = {
            "movie": "Inception",
            "tvshow": "Breaking Bad",
            "anime": "Attack on Titan",
            "manhwa": "Solo Leveling",
        }
        return examples.get(self.CATEGORY, "title")
