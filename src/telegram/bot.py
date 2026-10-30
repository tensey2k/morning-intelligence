"""
Telegram Bot for Morning Intelligence Assistant.
Handles all user interactions, commands, and scheduled delivery.
"""
import asyncio
import logging
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from src.config import settings
from src.briefing.engine import briefing_engine
from src.telegram.authorization import AuthorizationMiddleware
from src.telegram.commands import CommandHandler as CommandHandlerClass
from src.telegram.formatters import (
    format_briefing,
    format_markets,
    format_weather,
    format_news,
    format_status,
    format_help,
    format_settings,
)
from src.scheduler.manager import scheduler_manager
from src.settings_manager import settings_manager

logger = logging.getLogger(__name__)


class TelegramBot:
    """Main Telegram bot class."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.allowed_user_id = settings.telegram_allowed_user_id
        self.application: Optional[Application] = None
        self.auth = AuthorizationMiddleware(self.allowed_user_id)
        self.commands = CommandHandlerClass(self.auth, briefing_engine, settings_manager, scheduler_manager)

    async def initialize(self):
        """Initialize the Telegram application."""
        self.application = (
            ApplicationBuilder()
            .token(self.bot_token)
            .concurrent_updates(True)
            .build()
        )

        # Add authorization middleware
        self.application.add_handler(
            MessageHandler(filters.ALL, self.auth.check_authorization), group=-1
        )

        # Command handlers
        self.application.add_handler(CommandHandler("start", self.commands.start))
        self.application.add_handler(CommandHandler("help", self.commands.help))
        self.application.add_handler(CommandHandler("briefing", self.commands.briefing))
        self.application.add_handler(CommandHandler("markets", self.commands.markets))
        self.application.add_handler(CommandHandler("news", self.commands.news))
        self.application.add_handler(CommandHandler("weather", self.commands.weather))
        self.application.add_handler(CommandHandler("settings", self.commands.settings))
        self.application.add_handler(CommandHandler("status", self.commands.status))
        self.application.add_handler(CommandHandler("calendar", self.commands.calendar))
        self.application.add_handler(CommandHandler("mortgage", self.commands.mortgage))
        self.application.add_handler(CommandHandler("savings", self.commands.savings))

        # Callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self.commands.callback_handler))

        # Error handler
        self.application.add_error_handler(self._error_handler)

        logger.info("Telegram bot initialized")

    async def start(self):
        """Start the bot."""
        if not self.application:
            await self.initialize()

        # Initialize scheduler
        await scheduler_manager.initialize()

        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        logger.info("Telegram bot started")

    async def stop(self):
        """Stop the bot."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

        await scheduler_manager.shutdown()
        await briefing_engine.close()

        logger.info("Telegram bot stopped")

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler."""
        logger.error(f"Exception while handling update: {context.error}")

        # Send error to user if possible
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later or use /status to check system health."
                )
            except Exception:
                pass

    async def send_briefing(self, briefing, chat_id: Optional[int] = None) -> bool:
        """Send a briefing to the authorized user."""
        target_chat_id = chat_id or self.allowed_user_id

        try:
            formatted = format_briefing(briefing)

            for i, chunk in enumerate(formatted):
                await self.application.bot.send_message(
                    chat_id=target_chat_id,
                    text=chunk,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                # Small delay between chunks to avoid rate limits
                if i < len(formatted) - 1:
                    await asyncio.sleep(0.5)

            logger.info(f"Briefing sent to {target_chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send briefing: {e}")
            return False

    async def send_message(self, text: str, chat_id: Optional[int] = None, **kwargs) -> bool:
        """Send a simple message to the authorized user."""
        target_chat_id = chat_id or self.allowed_user_id

        try:
            await self.application.bot.send_message(
                chat_id=target_chat_id,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=kwargs.get("disable_web_page_preview", True),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def get_application(self) -> Optional[Application]:
        """Get the Telegram application instance."""
        return self.application


# Global instance
telegram_bot = TelegramBot()