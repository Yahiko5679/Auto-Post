"""
CosmicBotz — Pyrofork Client + aiohttp health server
The web server runs on Render's injected $PORT so the service
stays alive and health-checks pass.
"""
import logging
from aiohttp import web
from pyrofork import Client
import config as cfg

logger = logging.getLogger(__name__)

# ── Web routes ────────────────────────────────────────────────────────────────
CosmicBotz_Web = web.RouteTableDef()


@CosmicBotz_Web.get("/", allow_head=True)
async def root_handler(request):
    return web.json_response("CosmicBotz [AutoPost Generator]")


@CosmicBotz_Web.get("/health", allow_head=True)
async def health_handler(request):
    return web.json_response({"status": "ok", "bot": cfg.BOT_USERNAME})


async def web_server():
    app = web.Application(client_max_size=30_000_000)
    app.add_routes(CosmicBotz_Web)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host="0.0.0.0", port=cfg.PORT)
    await site.start()
    logger.info(f"🌐 Web server running on port {cfg.PORT}")


# ── Bot client ────────────────────────────────────────────────────────────────
class CosmicBotzClient(Client):
    def __init__(self):
        super().__init__(
            name="CosmicBotz",
            api_id=cfg.API_ID,
            api_hash=cfg.API_HASH,
            bot_token=cfg.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        logger.info(f"✅ CosmicBotz started as @{me.username}")
        # 🔹 Start Web Server (Render PORT keep-alive)
        await web_server()

    async def stop(self):
        await super().stop()
        logger.info("⛔ CosmicBotz stopped.")


CosmicBotz = CosmicBotzClient()
