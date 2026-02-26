"""
webserver.py — Render-compatible Webhook Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs the Telegram bot in webhook mode when MODE=webhook (Render/production).
Falls back to polling when MODE=polling (local development).

Features:
  • aiohttp web server — handles Telegram webhook POSTs
  • /health endpoint  — Render health checks hit this
  • /webhook endpoint — Telegram sends updates here
  • Auto-registers webhook URL with Telegram on startup
  • Graceful shutdown with proper cleanup
"""

import os
import sys
import logging
import asyncio
from aiohttp import web

from dotenv import load_dotenv
load_dotenv()

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
MODE            = os.getenv("MODE", "webhook").lower()
PORT            = int(os.getenv("PORT", 8080))
WEBHOOK_PATH    = os.getenv("WEBHOOK_PATH", "/webhook")
BOT_TOKEN       = os.getenv("BOT_TOKEN", "")

# Render sets RENDER_EXTERNAL_URL = https://your-service.onrender.com
# We construct the full webhook URL from it
_render_host = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL  = os.getenv("WEBHOOK_URL", f"{_render_host}{WEBHOOK_PATH}" if _render_host else "")

# Build time (shown in /health response)
BUILD_TIME = os.getenv("RENDER_SERVICE_DETAILS_UPDATEDAT", "unknown")


# ─────────────────────────────────────────────────────────────────────────────
# Application factory
# ─────────────────────────────────────────────────────────────────────────────

def build_application():
    """Build and return the configured python-telegram-bot Application."""
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        CallbackQueryHandler, filters,
    )
    from handlers.movie    import MovieHandler
    from handlers.tvshow   import TVShowHandler
    from handlers.anime    import AnimeHandler
    from handlers.manhwa   import ManhwaHandler
    from handlers.admin    import AdminHandler
    from handlers.settings import SettingsHandler
    from handlers.start    import StartHandler
    from handlers.template import TemplateHandler

    app = Application.builder().token(BOT_TOKEN).build()

    start_h    = StartHandler()
    movie_h    = MovieHandler()
    tvshow_h   = TVShowHandler()
    anime_h    = AnimeHandler()
    manhwa_h   = ManhwaHandler()
    admin_h    = AdminHandler()
    settings_h = SettingsHandler()
    template_h = TemplateHandler()

    # ── Commands ───────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",         start_h.start))
    app.add_handler(CommandHandler("help",          start_h.help_cmd))
    app.add_handler(CommandHandler("movie",         movie_h.search))
    app.add_handler(CommandHandler("tvshow",        tvshow_h.search))
    app.add_handler(CommandHandler("anime",         anime_h.search))
    app.add_handler(CommandHandler("manhwa",        manhwa_h.search))
    app.add_handler(CommandHandler("settings",      settings_h.menu))
    app.add_handler(CommandHandler("templates",     template_h.list_templates))
    app.add_handler(CommandHandler("myformat",      template_h.my_format))
    app.add_handler(CommandHandler("setformat",     template_h.set_format_start))
    app.add_handler(CommandHandler("setwatermark",  settings_h.set_watermark))
    app.add_handler(CommandHandler("setchannel",    settings_h.set_channel))
    app.add_handler(CommandHandler("stats",         start_h.stats))
    app.add_handler(CommandHandler("admin",         admin_h.panel))
    app.add_handler(CommandHandler("broadcast",     admin_h.broadcast))
    app.add_handler(CommandHandler("ban",           admin_h.ban_user))
    app.add_handler(CommandHandler("unban",         admin_h.unban_user))
    app.add_handler(CommandHandler("addpremium",    admin_h.add_premium))
    app.add_handler(CommandHandler("revokepremium", admin_h.revoke_premium))
    app.add_handler(CommandHandler("userinfo",      admin_h.user_info))
    app.add_handler(CommandHandler("globalstats",   admin_h.global_stats))

    # ── Inline button callbacks ────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(movie_h.callback,    pattern="^movie_"))
    app.add_handler(CallbackQueryHandler(tvshow_h.callback,   pattern="^tv_"))
    app.add_handler(CallbackQueryHandler(anime_h.callback,    pattern="^anime_"))
    app.add_handler(CallbackQueryHandler(manhwa_h.callback,   pattern="^manhwa_"))
    app.add_handler(CallbackQueryHandler(settings_h.callback, pattern="^settings_"))
    app.add_handler(CallbackQueryHandler(template_h.callback, pattern="^tpl_"))
    app.add_handler(CallbackQueryHandler(admin_h.callback,    pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(start_h.callback,    pattern="^start_"))

    # ── Message routing (photos + text for FSM steps) ─────────────────────────
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.PRIVATE, _route_photo
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, _route_text
    ))

    return app


async def _route_photo(update, context):
    from fsm.state_manager import StateManager
    from handlers.movie    import MovieHandler
    from handlers.tvshow   import TVShowHandler
    from handlers.anime    import AnimeHandler
    from handlers.manhwa   import ManhwaHandler

    sm    = StateManager()
    state = await sm.get_state(update.effective_user.id)
    if state and state.get("awaiting_thumbnail"):
        handlers = {
            "movie":   MovieHandler(),
            "tvshow":  TVShowHandler(),
            "anime":   AnimeHandler(),
            "manhwa":  ManhwaHandler(),
        }
        cat = state.get("category")
        if cat in handlers:
            await handlers[cat].handle_thumbnail(update, context)


async def _route_text(update, context):
    from fsm.state_manager import StateManager
    from handlers.template import TemplateHandler
    from handlers.settings import SettingsHandler
    from handlers.admin    import AdminHandler

    sm    = StateManager()
    state = await sm.get_state(update.effective_user.id)
    if not state:
        return

    if state.get("awaiting_template_name") or state.get("awaiting_template_body"):
        await TemplateHandler().handle_text(update, context)
    elif state.get("awaiting_watermark"):
        await SettingsHandler().handle_watermark_text(update, context)
    elif state.get("awaiting_channel"):
        await SettingsHandler().handle_channel_input(update, context)
    elif state.get("awaiting_broadcast"):
        await AdminHandler().handle_broadcast_text(update, context)


# ─────────────────────────────────────────────────────────────────────────────
# Webhook mode (Render production)
# ─────────────────────────────────────────────────────────────────────────────

async def run_webhook():
    """
    Start the aiohttp web server.
    - POST /webhook  → forward to python-telegram-bot
    - GET  /health   → Render health check (must return 200)
    - GET  /         → basic info page
    """
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not set. Exiting.")
        sys.exit(1)

    if not WEBHOOK_URL:
        logger.critical(
            "WEBHOOK_URL could not be determined. "
            "Set RENDER_EXTERNAL_URL or WEBHOOK_URL env var."
        )
        sys.exit(1)

    logger.info(f"🌐 Starting in WEBHOOK mode")
    logger.info(f"   Webhook URL : {WEBHOOK_URL}")
    logger.info(f"   Listen port : {PORT}")

    ptb_app = build_application()

    # ── aiohttp request handlers ───────────────────────────────────────────────

    async def handle_webhook(request: web.Request) -> web.Response:
        """Receive Telegram update and pass to PTB."""
        try:
            data = await request.json()
            from telegram import Update
            update = Update.de_json(data, ptb_app.bot)
            await ptb_app.process_update(update)
            return web.Response(status=200, text="ok")
        except Exception as e:
            logger.error(f"Webhook handler error: {e}", exc_info=True)
            return web.Response(status=500, text="error")

    async def handle_health(request: web.Request) -> web.Response:
        """Render calls this every 30s. Must return 200."""
        return web.json_response({
            "status": "ok",
            "mode":   "webhook",
            "bot":    os.getenv("BOT_USERNAME", "unknown"),
            "build":  BUILD_TIME,
        })

    async def handle_root(request: web.Request) -> web.Response:
        return web.Response(
            text="🤖 AutoPost Bot is running.\n/health for status.",
            content_type="text/plain",
        )

    # ── Build aiohttp app ──────────────────────────────────────────────────────
    aio_app = web.Application()
    aio_app.router.add_post(WEBHOOK_PATH, handle_webhook)
    aio_app.router.add_get("/health",     handle_health)
    aio_app.router.add_get("/",           handle_root)

    # ── Startup: init PTB, register webhook ───────────────────────────────────
    async def on_startup(app):
        await ptb_app.initialize()
        await ptb_app.start()

        # Delete any old webhook / polling session, then register new one
        await ptb_app.bot.delete_webhook(drop_pending_updates=True)
        await ptb_app.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query", "inline_query"],
            drop_pending_updates=True,
        )
        info = await ptb_app.bot.get_webhook_info()
        logger.info(f"✅ Webhook registered: {info.url}")
        logger.info(f"   Pending updates  : {info.pending_update_count}")

    # ── Shutdown: deregister webhook, stop PTB ────────────────────────────────
    async def on_shutdown(app):
        logger.info("⏹  Shutting down...")
        await ptb_app.bot.delete_webhook()
        await ptb_app.stop()
        await ptb_app.shutdown()
        logger.info("✅ Shutdown complete.")

    aio_app.on_startup.append(on_startup)
    aio_app.on_shutdown.append(on_shutdown)

    # ── Run ───────────────────────────────────────────────────────────────────
    runner = web.AppRunner(aio_app, access_log=logger)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()

    logger.info(f"🚀 Server listening on 0.0.0.0:{PORT}")

    # Keep alive until cancelled
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await runner.cleanup()


# ─────────────────────────────────────────────────────────────────────────────
# Polling mode (local development)
# ─────────────────────────────────────────────────────────────────────────────

async def run_polling():
    """Local development mode — no server needed."""
    from telegram import Update

    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not set. Exiting.")
        sys.exit(1)

    logger.info("🔄 Starting in POLLING mode (local dev)")
    ptb_app = build_application()
    await ptb_app.bot.delete_webhook(drop_pending_updates=True)
    await ptb_app.run_polling(allowed_updates=Update.ALL_TYPES)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"🤖 AutoPost Bot starting | MODE={MODE.upper()}")

    if MODE == "polling":
        # python-telegram-bot handles its own event loop in polling mode
        import main as m
        m.main()
    else:
        # Webhook: run our aiohttp server
        try:
            asyncio.run(run_webhook())
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
