import os
import sys
_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)

import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, ADMIN_IDS, PORT, WEBHOOK_URL
from routers import get_all_routers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
LOGGER = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


async def on_startup():
    # Register all routers
    all_routers = get_all_routers()
    for router in all_routers:
        dp.include_router(router)
    LOGGER.info(f"✅ Loaded {len(all_routers)} routers")

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="<b><blockquote>🤖 CosmicBotz Started ✅</blockquote></b>",
            )
        except Exception as e:
            LOGGER.warning(f"Could not notify admin {admin_id}: {e}")

    # Set webhook
    webhook = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook, drop_pending_updates=True)
    LOGGER.info(f"✅ Webhook set → {webhook}")


async def on_shutdown():
    await bot.delete_webhook()
    LOGGER.info("⛔ Webhook deleted.")


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="CosmicBotz Running!"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    LOGGER.info(f"🌐 Starting on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
