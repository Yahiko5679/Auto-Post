import asyncio
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, PORT, ADMIN_IDS
from routers import get_all_routers
from utils.font_loader import ensure_fonts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


# ── Health server (Render uptime) ─────────────────────────────────────────────
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


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    ensure_fonts()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    for router in get_all_routers():
        dp.include_router(router)

    logger.info("✅ Routers loaded")

    # ✅ Remove webhook (important when switching modes)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
    except Exception as e:
        logger.warning(f"Webhook cleanup failed: {e}")

    # ✅ Start health server (only once)
    await start_health_server(PORT)

    # ✅ Delay to avoid instance overlap (Render fix)
    logger.info("⏳ Waiting before polling...")
    await asyncio.sleep(8)

    # ✅ Notify admin once
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "<b><blockquote>🤖 CosmicBotz Started </blockquote></b>"
            )
        except Exception:
            pass

    #  Start polling (NO LOOP, NO GATHER)
    logger.info("🚀 Polling started")
    await dp.start_polling(bot, skip_updates=True)


