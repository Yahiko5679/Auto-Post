import os
import sys
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from config import BOT_TOKEN, ADMIN_IDS
from routers import get_all_routers

PORT         = int(os.environ.get("PORT", 8080))
WEBHOOK_URL  = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_PATH = "/webhook"

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing!")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL is missing!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
LOGGER = logging.getLogger("bot")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

all_routers = get_all_routers()
for router in all_routers:
    dp.include_router(router)
LOGGER.info(f"✅ Loaded {len(all_routers)} routers")


async def on_startup(bot: Bot):
    webhook = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook, drop_pending_updates=True)
    LOGGER.info(f"✅ Webhook set → {webhook}")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="<b><blockquote>🤖 CosmicBotz Started ✅</blockquote></b>",
            )
        except Exception as e:
            LOGGER.warning(f"Could not notify admin {admin_id}: {e}")


async def on_shutdown(bot: Bot):
    LOGGER.info("⛔ Shutting down...")
    await bot.delete_webhook()
    await bot.session.close()


def main():
    # Register ONCE on dp — do NOT also add to aiohttp app signals
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="CosmicBotz Running!"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    app.router.add_get(WEBHOOK_PATH, lambda r: web.Response(text="Webhook OK"))

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    # NO on_startup/on_shutdown params here — setup_application doesn't support them
    # and it was causing double-trigger shutdown
    setup_application(app, dp, bot=bot)

    LOGGER.info(f"🌐 Starting on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()