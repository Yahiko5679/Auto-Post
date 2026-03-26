import os
import sys
_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)
import asyncio
import logging
import threading
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN, ADMIN_IDS, PORT
from routers import get_all_routers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
LOGGER = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


async def on_startup():
    # Register all routers
    for router in get_all_routers():
        dp.include_router(router)
    LOGGER.info(f"✅ Loaded {len(dp.routers)} routers")

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="<b><blockquote>🤖 CosmicBotz Started </blockquote></b>",
            )
        except Exception as e:
            LOGGER.warning(f"Could not notify admin {admin_id}: {e}")

    LOGGER.info("🚀 Bot started in polling mode")


async def on_shutdown():
    LOGGER.info("⛔ Bot shutting down.")


def run_dummy_web_server():
    """Dummy aiohttp web server to keep Render happy (health checks)."""
    async def _serve():
        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="CosmicBotz Running!"))
        app.router.add_get("/health", lambda r: web.Response(text="OK"))

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
        await site.start()
        LOGGER.info(f"🌐 web server listening on port {PORT}")
        # Keep running forever
        while True:
            await asyncio.sleep(3600)

    asyncio.run(_serve())


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start the dummy web server in a background daemon thread
    web_thread = threading.Thread(target=run_dummy_web_server, daemon=True)
    web_thread.start()

    # Run the bot in polling mode (blocking)
    LOGGER.info("🔄 Starting polling...")
    asyncio.run(dp.start_polling(bot, drop_pending_updates=True))