"""
Telegram Bot Channel for Morning Intelligence Assistant.
Implements commands: /start, /briefing, /markets, /news, /weather, /settings, /status, /help
"""
import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from src.config import settings
from src.briefing.engine import briefing_engine
from src.models import BriefingStatus, DeliveryAttempt, DeliveryChannel, DeliveryStatus
from src.settings_manager import settings_manager

logger = logging.getLogger(__name__)


class TelegramChannel:
    """Telegram bot channel for delivering briefings and handling commands."""

    def __init__(self):
        self.token = settings.telegram_bot_token
        self.allowed_user_id = settings.telegram_allowed_user_id
        self.application: Optional[Application] = None
        self._bot = None

    async def initialize(self):
        """Initialize the Telegram application."""
        self.application = (
            Application.builder()
            .token(self.token)
            .build()
        )

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("briefing", self.cmd_briefing))
        self.application.add_handler(CommandHandler("markets", self.cmd_markets))
        self.application.add_handler(CommandHandler("news", self.cmd_news))
        self.application.add_handler(CommandHandler("weather", self.cmd_weather))
        self.application.add_handler(CommandHandler("settings", self.cmd_settings))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("help", self.cmd_help))

        # Add message handler for unauthorized users
        self.application.add_handler(
            MessageHandler(filters.ALL & ~filters.User(user_id=self.allowed_user_id), self.handle_unauthorized)
        )

        # Set bot commands
        await self.set_bot_commands()

        logger.info("Telegram channel initialized")

    async def set_bot_commands(self):
        """Set bot command menu."""
        commands = [
            BotCommand("start", "Start the bot and show welcome message"),
            BotCommand("briefing", "Get today's full morning briefing"),
            BotCommand("markets", "Get current market snapshot"),
            BotCommand("news", "Get top financial news"),
            BotCommand("weather", "Get weather for Montreal and Casablanca"),
            BotCommand("settings", "View and modify settings"),
            BotCommand("status", "Check briefing generation and delivery status"),
            BotCommand("help", "Show help message"),
        ]
        await self.application.bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(chat_id=self.allowed_user_id),
        )

    def _check_authorization(self, update: Update) -> bool:
        """Check if user is authorized."""
        user_id = update.effective_user.id if update.effective_user else None
        return user_id == self.allowed_user_id

    async def handle_unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages from unauthorized users."""
        user_id = update.effective_user.id if update.effective_user else "unknown"
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        if update.message:
            await update.message.reply_text(
                "🚫 Unauthorized. This bot is for personal use only."
            )

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._check_authorization(update):
            return

        welcome = (
            "🌅 *Morning Intelligence Assistant*\n\n"
            "Your daily financial intelligence briefing delivered at 7:00 AM Toronto time.\n\n"
            "*Available commands:*\n"
            "📋 /briefing - Full morning briefing\n"
            "📈 /markets - Market snapshot (oil, crypto, rates, indices, FX)\n"
            "🌍 /news - Top financial news\n"
            "🌤️ /weather - Weather for Montreal & Casablanca\n"
            "⚙️ /settings - View/modify settings\n"
            "📊 /status - Briefing generation & delivery status\n"
            "❓ /help - This help message\n\n"
            f"*Timezone:* {settings.timezone}\n"
            f"*Delivery:* {settings.briefing_hour:02d}:{settings.briefing_minute:02d} daily\n"
            f"*Mode:* {settings.briefing_mode.capitalize()}"
        )
        await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available commands and examples."""
        if not self._check_authorization(update):
            return
        await self.cmd_start(update, context)

    async def cmd_briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /briefing command - generate and send full briefing."""
        if not self._check_authorization(update):
            return

        await update.message.reply_text("🔄 Generating your morning briefing...")

        try:
            briefing = await briefing_engine.generate_full_briefing()

            if briefing.status == BriefingStatus.GENERATED:
                await self._send_briefing_chunks(update, briefing)
            else:
                await update.message.reply_text(
                    f"❌ Failed to generate briefing: {briefing.error}"
                )
        except Exception as e:
            logger.error(f"Briefing generation error: {e}")
            await update.message.reply_text(f"❌ Error generating briefing: {e}")

    async def cmd_markets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /markets command - market snapshot."""
        if not self._check_authorization(update):
            return

        await update.message.reply_text("📈 Fetching market data...")

        try:
            # Generate compact briefing for markets focus
            briefing = await briefing_engine.generate_compact_briefing()

            if briefing.status == BriefingStatus.GENERATED:
                # Extract just markets section
                markets_text = self._format_markets_section(briefing)
                await update.message.reply_text(markets_text, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(f"❌ Failed: {briefing.error}")
        except Exception as e:
            logger.error(f"Markets command error: {e}")
            await update.message.reply_text(f"❌ Error fetching markets: {e}")

    async def cmd_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /news command - top financial news."""
        if not self._check_authorization(update):
            return

        await update.message.reply_text("🌍 Fetching latest news...")

        try:
            from src.data_sources.manager import data_source_manager
            news = await data_source_manager.get_top_news(15)

            if not news:
                await update.message.reply_text("No news available at the moment.")
                return

            lines = ["📰 *TOP FINANCIAL NEWS*", ""]
            for i, item in enumerate(news, 1):
                time_str = item.published_at.strftime("%H:%M UTC") if item.published_at else "Unknown time"
                lines.append(f"{i}. *{item.headline}*")
                lines.append(f"   {item.summary[:200]}...")
                lines.append(f"   📍 {', '.join(item.regions)} | 🕕 {time_str} | [Source]({item.url})")
                lines.append("")

            text = "\n".join(lines)
            chunks = briefing_engine.templates.split_message(text, settings.max_message_length)
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"News command error: {e}")
            await update.message.reply_text(f"❌ Error fetching news: {e}")

    async def cmd_weather(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /weather command - weather for Montreal and Casablanca."""
        if not self._check_authorization(update):
            return

        await update.message.reply_text("🌤️ Fetching weather...")

        try:
            from src.data_sources.manager import data_source_manager
            montreal = await data_source_manager.get_weather()
            casablanca = await data_source_manager.get_morocco_weather()

            lines = ["🌤️ *WEATHER FORECAST*", ""]

            for weather in [montreal, casablanca]:
                if weather:
                    lines.append(f"*{weather.city}, {weather.country}*")
                    if weather.current_temp_c is not None:
                        lines.append(f"  🌡️ Current: {weather.current_temp_c}°C")
                    if weather.feels_like_c is not None:
                        lines.append(f"  🤗 Feels like: {weather.feels_like_c}°C")
                    if weather.high_temp_c is not None and weather.low_temp_c is not None:
                        lines.append(f"  📊 High/Low: {weather.high_temp_c}°C / {weather.low_temp_c}°C")
                    if weather.precipitation_probability_pct is not None:
                        lines.append(f"  🌧️ Rain chance: {weather.precipitation_probability_pct}%")
                    if weather.snow_probability_pct is not None:
                        lines.append(f"  ❄️ Snow chance: {weather.snow_probability_pct}%")
                    if weather.wind_speed_kmh is not None:
                        lines.append(f"  💨 Wind: {weather.wind_speed_kmh} km/h {weather.wind_direction or ''}")
                    if weather.weather_description:
                        lines.append(f"  ☁️ {weather.weather_description}")
                    if weather.alerts:
                        for alert in weather.alerts:
                            lines.append(f"  ⚠️ *ALERT:* {alert}")
                    lines.append("")

            text = "\n".join(lines)
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Weather command error: {e}")
            await update.message.reply_text(f"❌ Error fetching weather: {e}")

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command - view and modify settings."""
        if not self._check_authorization(update):
            return

        # Get current settings from in-memory manager
        user_settings = await settings_manager.get_user_settings(self.allowed_user_id)

        text = (
            "⚙️ *CURRENT SETTINGS*\n\n"
            f"🕐 *Timezone:* {user_settings.get('timezone', settings.timezone) if user_settings else settings.timezone}\n"
            f"⏰ *Briefing time:* {user_settings.get('briefing_hour', settings.briefing_hour) if user_settings else settings.briefing_hour:02d}:{user_settings.get('briefing_minute', settings.briefing_minute) if user_settings else settings.briefing_minute:02d}\n"
            f"📅 *Weekdays only:* {'Yes' if (user_settings.get('schedule_weekdays_only', settings.schedule_weekdays_only) if user_settings else settings.schedule_weekdays_only) else 'No'}\n"
            f"🌤️ *Weather city:* {user_settings.get('weather_city', settings.weather_city) if user_settings else settings.weather_city}, {user_settings.get('weather_country', settings.weather_country) if user_settings else settings.weather_country}\n"
            f"🇲🇦 *Morocco weather:* {user_settings.get('morocco_weather_city', settings.morocco_weather_city) if user_settings else settings.morocco_weather_city}, {user_settings.get('morocco_weather_country', settings.morocco_weather_country) if user_settings else settings.morocco_weather_country}\n"
            f"🌐 *Language:* {user_settings.get('default_language', settings.default_language) if user_settings else settings.default_language}\n"
            f"📝 *Briefing mode:* {user_settings.get('briefing_mode', settings.briefing_mode) if user_settings else settings.briefing_mode}\n\n"
            "*To modify settings, use the web interface or contact admin.*"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - check briefing generation and delivery status."""
        if not self._check_authorization(update):
            return

        try:
            # Get health checks
            from src.data_sources.manager import data_source_manager
            health = await data_source_manager.health_check_all()

            # Get next scheduled run
            from src.scheduler.manager import scheduler_manager
            next_run = await scheduler_manager.get_next_run()

            # Get last briefing status
            from src.settings_manager import settings_manager
            last_briefing = await settings_manager.get_latest_briefing()

            # Get scheduler status
            scheduler_status = scheduler_manager.get_status()

            await update.message.reply_text(
                format_status(health, next_run, last_briefing, scheduler_status),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Status command error: {e}")
            await update.message.reply_text(
                f"❌ Error checking status: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # DELIVERY METHODS
    # =========================================================================
    async def _send_briefing_chunks(self, update: Update, briefing):
        """Send briefing in chunks respecting Telegram limits."""
        chunks = briefing.formatted_chunks if hasattr(briefing, 'formatted_chunks') else [briefing.formatted_markdown]

        for i, chunk in enumerate(chunks):
            try:
                if i == 0:
                    await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                else:
                    await update.message.reply_text(f"(cont.)\n\n{chunk}", parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Failed to send chunk {i}: {e}")
                # Try without markdown
                try:
                    await update.message.reply_text(chunk, disable_web_page_preview=True)
                except Exception:
                    pass

    async def send_briefing(self, briefing) -> List[DeliveryAttempt]:
        """Send briefing to the authorized user via Telegram."""
        attempts = []

        for chunk in briefing.formatted_chunks:
            attempt = DeliveryAttempt(
                briefing_id=briefing.id,
                channel=DeliveryChannel.TELEGRAM,
                recipient_id=str(self.allowed_user_id),
                status=DeliveryStatus.PENDING,
            )

            try:
                message = await self.application.bot.send_message(
                    chat_id=self.allowed_user_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                attempt.status = DeliveryStatus.SENT
                attempt.provider_message_id = str(message.message_id)
                attempt.sent_at = datetime.now(timezone.utc)
            except Exception as e:
                attempt.status = DeliveryStatus.FAILED
                attempt.error = str(e)
                logger.error(f"Telegram send failed: {e}")

            attempt.updated_at = datetime.now(timezone.utc)
            attempts.append(attempt)

        return attempts

    def _format_markets_section(self, briefing) -> str:
        """Format markets section for /markets command."""
        lines = ["📈 *MARKET SNAPSHOT*", ""]

        # Oil
        if "oil" in briefing.markets:
            oil = briefing.markets["oil"]
            if oil:
                lines.append("*OIL*")
                for o in oil:
                    if hasattr(o, 'benchmark'):
                        lines.append(f"  {o.benchmark}: ${o.price_per_barrel:.2f}/bbl")
                lines.append("")

        # Crypto
        if "crypto" in briefing.markets:
            crypto = briefing.markets["crypto"]
            if crypto:
                lines.append("*CRYPTO*")
                for c in crypto:
                    if hasattr(c, 'symbol'):
                        cad = f" (C${c.price_cad:,.0f})" if c.price_cad else ""
                        change = f" ({c.change_24h_pct:+.1f}%)" if c.change_24h_pct else ""
                        lines.append(f"  {c.symbol}: ${c.price_usd:,.0f}{cad}{change}")
                lines.append("")

        # Canadian Bonds
        if "bonds" in briefing.markets:
            bonds = briefing.markets["bonds"]
            if bonds:
                lines.append("*CANADIAN BOND YIELDS*")
                for b in bonds:
                    if hasattr(b, 'country') and b.country == "CA" and hasattr(b, 'maturity_years'):
                        if b.maturity_years in (2, 5, 10):
                            lines.append(f"  {b.maturity_years}Y: {b.yield_pct:.2f}%")
                lines.append("")

        # Policy Rates
        if "policy_rates" in briefing.markets:
            rates = briefing.markets["policy_rates"]
            if rates:
                lines.append("*POLICY RATES*")
                for r in rates:
                    if hasattr(r, 'country') and r.maturity_years == 0:
                        lines.append(f"  {r.country} Policy: {r.yield_pct:.2f}%")
                lines.append("")

        # Indices
        if "indices" in briefing.markets:
            indices = briefing.markets["indices"]
            if indices:
                lines.append("*STOCK INDICES*")
                key_indices = ["S&P 500", "Nasdaq", "Dow Jones", "S&P/TSX", "Euro Stoxx 50", "CAC 40", "FTSE 100", "Nikkei 225", "Hang Seng"]
                for idx in indices:
                    if hasattr(idx, 'index_name') and any(k in idx.index_name for k in key_indices):
                        lines.append(f"  {idx.index_name}: {idx.index_value:,.0f}")
                lines.append("")

        # FX
        if "forex" in briefing.markets:
            forex = briefing.markets["forex"]
            if forex:
                lines.append("*FOREX*")
                key_pairs = ["USD/CAD", "EUR/CAD", "USD/MAD", "EUR/USD"]
                for f in forex:
                    if hasattr(f, 'base_currency') and hasattr(f, 'quote_currency'):
                        pair = f"{f.base_currency}/{f.quote_currency}"
                        if pair in key_pairs:
                            lines.append(f"  {pair}: {f.rate:.4f}")
                lines.append("")

        return "\n".join(lines)

    async def start_polling(self):
        """Start the bot polling."""
        if self.application:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            logger.info("Telegram bot started polling")

    async def stop_polling(self):
        """Stop the bot polling."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")


# Global instance
telegram_channel = TelegramChannel()