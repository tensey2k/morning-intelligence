"""
Main entry point for Morning Intelligence Assistant.
"""
import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from aiohttp import web
from src.config import settings
from src.storage.database import init_db, close_db
from src.telegram.bot import telegram_bot
from src.scheduler.manager import scheduler_manager
from src.briefing.engine import briefing_engine
from src.data_sources.manager import data_source_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("morning_intelligence.log"),
    ],
)

logger = logging.getLogger(__name__)


# Health check HTTP server
async def health_check(request):
    """Health check endpoint for Docker."""
    try:
        # Check critical components
        health = await data_source_manager.health_check_all()
        all_healthy = all(health.values())

        return web.json_response({
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": asyncio.get_event_loop().time(),
            "components": health,
        }, status=200 if all_healthy else 503)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return web.json_response({
            "status": "unhealthy",
            "error": str(e),
        }, status=503)


async def start_health_server():
    """Start the health check HTTP server."""
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check server started on port 8080")
    return runner


class MorningIntelligenceApp:
    """Main application class."""

    def __init__(self):
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._health_runner = None

    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Morning Intelligence Assistant...")

        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Initialize Telegram bot
        await telegram_bot.initialize()
        logger.info("Telegram bot initialized")

        # Initialize scheduler
        await scheduler_manager.initialize()
        logger.info("Scheduler initialized")

        # Start health check server
        self._health_runner = await start_health_server()

        logger.info("All components initialized successfully")

    async def start(self):
        """Start the application."""
        if self.running:
            return

        self.running = True
        logger.info("Starting Morning Intelligence Assistant...")

        # Start Telegram bot (this blocks)
        await telegram_bot.start()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def stop(self):
        """Stop the application gracefully."""
        if not self.running:
            return

        logger.info("Stopping Morning Intelligence Assistant...")
        self.running = False

        # Stop Telegram bot
        await telegram_bot.stop()

        # Stop health check server
        if self._health_runner:
            await self._health_runner.cleanup()

        # Close database
        await close_db()

        self._shutdown_event.set()
        logger.info("Morning Intelligence Assistant stopped")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(self.stop())


async def main():
    """Main entry point."""
    app = MorningIntelligenceApp()

    # Set up signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, app.signal_handler, sig, None)

    try:
        await app.initialize()
        await app.start()
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        await app.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())