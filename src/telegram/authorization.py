"""
Authorization middleware for Telegram bot.
Restricts access to authorized user only.
"""
import logging
from typing import Callable, Awaitable, Any

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class AuthorizationMiddleware:
    """Middleware to restrict bot access to authorized user only."""

    def __init__(self, allowed_user_id: int):
        self.allowed_user_id = allowed_user_id

    async def check_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Check if the update is from an authorized user.
        Returns True if authorized, False if not (and sends rejection message).
        """
        user = update.effective_user
        chat = update.effective_chat

        if not user:
            return True  # Let other handlers deal with it

        user_id = user.id

        # Check if user is authorized
        if user_id != self.allowed_user_id:
            logger.warning(f"Unauthorized access attempt from user {user_id} (@{user.username})")

            # Send rejection message
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        "🔒 **Unauthorized Access**\n\n"
                        "This is a private morning intelligence assistant. "
                        "Access is restricted to the authorized user only.\n\n"
                        f"Your user ID: `{user_id}`\n"
                        "If you believe this is an error, contact the administrator."
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to send rejection message: {e}")

            return False

        return True

    def is_authorized(self, user_id: int) -> bool:
        """Check if a user ID is authorized."""
        return user_id == self.allowed_user_id

    def get_allowed_user_id(self) -> int:
        """Get the authorized user ID."""
        return self.allowed_user_id


async def authorize_only(
    handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]:
    """
    Decorator to restrict a handler to authorized users only.
    Use this on individual command handlers if needed.
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from src.config import settings
        auth = AuthorizationMiddleware(settings.telegram_allowed_user_id)

        if not await auth.check_authorization(update, context):
            return

        return await handler(update, context)

    return wrapper