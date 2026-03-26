import asyncio
import logging

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, PORT, ADMIN_IDS
from routers import get_all_routers
from utils.font_loader import ensure_fonts

logger = logging.getLogger("bot")

# Global flag to prevent multiple start messages
_bot_started = False


# ── Health Server (Render Uptime) ───────────────────────────────────────────
async def _handle_ping(request):
    return web.Response(text="OK")


async def _handle_health(request):
    return web.Response(
        content_type="application/json",
        text='{"status":"ok","bot":"CosmicBotz"}'
    )


async def start_health_server(port: int):
    app = web.Application()
    app.router.add_get("/", _handle_ping)
    app.router.add_get("/health", _handle_health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"🌐 Health server running on port {port}")


# ── Graceful Shutdown ───────────────────────────────────────────────────────
async def shutdown(bot: Bot, dp: Dispatcher):
    logger.info("🛑 Cleaning up bot resources...")
    try:
        await bot.session.close()
    except Exception:
        pass
    logger.info("✅ Bot resources closed.")


# ── Main Bot Runner ─────────────────────────────────────────────────────────
async def run_bot():
    global _bot_started

    ensure_fonts()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # Include all routers
    for router in get_all_routers():
        dp.include_router(router)

    logger.info("✅ All routers loaded successfully")

    # Clean webhook + drop pending updates
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted and pending updates dropped")
        await asyncio.sleep(2)
    except Exception as e:
        logger.warning(f"Webhook cleanup failed: {e}")

    # Start health server
    await start_health_server(PORT)

    # Important delay to prevent instance overlap on Render
    logger.info("⏳ Waiting before polling to avoid Telegram conflicts...")
    await asyncio.sleep(12)

    try:
        logger.info("🚀 Starting long polling...")

        # Send start notification only once
        if not _bot_started:
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        "<b><blockquote>🤖 CosmicBotz Started Successfully</blockquote></b>"
                    )
                except Exception as e:
                    logger.warning(f"Could not notify admin {admin_id}: {e}")
            _bot_started = True

        # Start polling
        await dp.start_polling(
            bot,
            skip_updates=True,
            allowed_updates=dp.resolve_used_update_types(),
        )

    except asyncio.CancelledError:
        logger.info("Polling was cancelled.")
    except Exception as e:
        logger.error(f"Polling stopped with error: {e}", exc_info=True)
    finally:
        await shutdown(bot, dp)