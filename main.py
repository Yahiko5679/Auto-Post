"""
AutoPost Generator Bot - Main Entry Point
Full Advanced System | All Categories | Public + Admin Controls
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from config import BOT_TOKEN
from handlers.movie import MovieHandler
from handlers.tvshow import TVShowHandler
from handlers.anime import AnimeHandler
from handlers.manhwa import ManhwaHandler
from handlers.admin import AdminHandler
from handlers.settings import SettingsHandler
from handlers.start import StartHandler
from handlers.template import TemplateHandler
from fsm.states import (
    THUMBNAIL_UPLOAD,
    FORMAT_SELECT,
    WATERMARK_TEXT,
    CHANNEL_LINK,
    TEMPLATE_NAME,
    TEMPLATE_BODY,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    start_handler = StartHandler()
    movie_handler = MovieHandler()
    tvshow_handler = TVShowHandler()
    anime_handler = AnimeHandler()
    manhwa_handler = ManhwaHandler()
    admin_handler = AdminHandler()
    settings_handler = SettingsHandler()
    template_handler = TemplateHandler()

    # ── Core Commands ──────────────────────────────────────────
    app.add_handler(CommandHandler("start", start_handler.start))
    app.add_handler(CommandHandler("help", start_handler.help_cmd))
    app.add_handler(CommandHandler("movie", movie_handler.search))
    app.add_handler(CommandHandler("tvshow", tvshow_handler.search))
    app.add_handler(CommandHandler("anime", anime_handler.search))
    app.add_handler(CommandHandler("manhwa", manhwa_handler.search))

    # ── Settings & Templates ───────────────────────────────────
    app.add_handler(CommandHandler("settings", settings_handler.menu))
    app.add_handler(CommandHandler("templates", template_handler.list_templates))
    app.add_handler(CommandHandler("myformat", template_handler.my_format))
    app.add_handler(CommandHandler("setformat", template_handler.set_format_start))
    app.add_handler(CommandHandler("setwatermark", settings_handler.set_watermark))
    app.add_handler(CommandHandler("setchannel", settings_handler.set_channel))
    app.add_handler(CommandHandler("stats", start_handler.stats))

    # ── Admin Commands ─────────────────────────────────────────
    app.add_handler(CommandHandler("admin", admin_handler.panel))
    app.add_handler(CommandHandler("broadcast", admin_handler.broadcast))
    app.add_handler(CommandHandler("ban", admin_handler.ban_user))
    app.add_handler(CommandHandler("unban", admin_handler.unban_user))
    app.add_handler(CommandHandler("addpremium", admin_handler.add_premium))
    app.add_handler(CommandHandler("revokepremium", admin_handler.revoke_premium))
    app.add_handler(CommandHandler("userinfo", admin_handler.user_info))
    app.add_handler(CommandHandler("globalstats", admin_handler.global_stats))

    # ── Callback Query Handler (all inline buttons) ────────────
    app.add_handler(CallbackQueryHandler(movie_handler.callback,    pattern="^movie_"))
    app.add_handler(CallbackQueryHandler(tvshow_handler.callback,   pattern="^tv_"))
    app.add_handler(CallbackQueryHandler(anime_handler.callback,    pattern="^anime_"))
    app.add_handler(CallbackQueryHandler(manhwa_handler.callback,   pattern="^manhwa_"))
    app.add_handler(CallbackQueryHandler(settings_handler.callback, pattern="^settings_"))
    app.add_handler(CallbackQueryHandler(template_handler.callback, pattern="^tpl_"))
    app.add_handler(CallbackQueryHandler(admin_handler.callback,    pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(start_handler.callback,    pattern="^start_"))

    # ── Message Handler (thumbnail uploads, text inputs) ───────
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.PRIVATE,
        _route_photo
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        _route_text
    ))

    logger.info("🚀 AutoPost Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


async def _route_photo(update: Update, context):
    """Route photo messages to active FSM state handler."""
    from fsm.state_manager import StateManager
    sm = StateManager()
    state = await sm.get_state(update.effective_user.id)

    if state and state.get("awaiting_thumbnail"):
        category = state.get("category")
        handlers = {
            "movie": MovieHandler(),
            "tvshow": TVShowHandler(),
            "anime": AnimeHandler(),
            "manhwa": ManhwaHandler(),
        }
        if category in handlers:
            await handlers[category].handle_thumbnail(update, context)


async def _route_text(update: Update, context):
    """Route text messages to active FSM state handler."""
    from fsm.state_manager import StateManager
    sm = StateManager()
    state = await sm.get_state(update.effective_user.id)

    if not state:
        return

    from handlers.template import TemplateHandler
    from handlers.settings import SettingsHandler

    if state.get("awaiting_template_name") or state.get("awaiting_template_body"):
        await TemplateHandler().handle_text(update, context)
    elif state.get("awaiting_watermark"):
        await SettingsHandler().handle_watermark_text(update, context)
    elif state.get("awaiting_channel"):
        await SettingsHandler().handle_channel_input(update, context)
    elif state.get("awaiting_broadcast") :
        await AdminHandler().handle_broadcast_text(update, context)


if __name__ == "__main__":
    main()
