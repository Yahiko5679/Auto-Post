"""
CosmicBotz — Entry Point
Run: python main.py
"""
import asyncio
import logging
import os
from bot import CosmicBotz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    os.makedirs("assets/fonts", exist_ok=True)
    os.makedirs("temp", exist_ok=True)

    async with CosmicBotz:
        logger.info("🚀 CosmicBotz is running...")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
