import asyncio
import logging
import sys
import uvicorn

from bot.config import DASHBOARD_PORT
from bot.exchange import close_exchange
from bot.trader import init_db
from dashboard.app import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def main():
    await init_db()
    logger.info("Database initialized")
    logger.info("Starting dashboard on http://0.0.0.0:%d", DASHBOARD_PORT)

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=DASHBOARD_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        await close_exchange()
        logger.info("Exchange connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
