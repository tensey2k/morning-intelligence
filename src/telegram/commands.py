"""
Command handlers for Telegram bot.
Implements all user commands: /start, /help, /briefing, /markets, /news, /weather, /settings, /status, /calendar, /mortgage, /savings
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from src.config import settings
from src.briefing.engine import briefing_engine
from src.data_sources.manager import data_source_manager
from src.storage.repository import repository
from src.telegram.formatters import (
    format_briefing,
    format_markets,
    format_weather,
    format_news,
    format_status,
    format_help,
    format_settings,
    format_calendar,
    format_mortgage,
    format_savings,
)
from src.telegram.authorization import AuthorizationMiddleware

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handles all Telegram bot commands."""

    def __init__(
        self,
        auth: AuthorizationMiddleware,
        engine,
        repo,
        scheduler,
    ):
        self.auth = auth
        self.engine = engine
        self.repo = repo
        self.scheduler = scheduler

    # =========================================================================
    # BASIC COMMANDS
    # =========================================================================
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Initialize the bot and explain how to use it."""
        user = update.effective_user
        welcome_text = (
            f"🌅 **Welcome to Morning Intelligence Assistant!**\n\n"
            f"Hello {user.first_name}! I'm your personal morning briefing bot.\n\n"
            f"**What I do:**\n"
            f"• 📅 Automatically send you a daily morning briefing at {settings.briefing_hour:02d}:{settings.briefing_minute:02d} {settings.timezone}\n"
            f"• 📊 Provide on-demand market data, news, weather, and economic calendar\n"
            f"• 🏠 Focus on Canadian mortgages, savings, and macroeconomic intelligence\n"
            f"• 🇲🇦 Include Morocco-relevant data (weather, news, economics)\n\n"
            f"**Available Commands:**\n"
            f"• `/briefing` — Get your latest morning briefing\n"
            f"• `/markets` — Current market indicators (oil, crypto, bonds, stocks, FX)\n"
            f"• `/news` — Top financial news (Canada, US, Morocco, Global)\n"
            f"• `/weather` — Weather for Montreal (and Casablanca)\n"
            f"• `/calendar` — Economic calendar (today + 7 days)\n"
            f"• `/mortgage` — Mortgage analyst intelligence\n"
            f"• `/savings` — Savings & personal finance updates\n"
            f"• `/settings` — View/change preferences\n"
            f"• `/status` — System health and next scheduled run\n"
            f"• `/help` — This help message\n\n"
            f"**Data Sources:** Bank of Canada, Alpha Vantage, FRED, EIA, CoinGecko, Open-Meteo, MarketAux, RSS feeds\n\n"
            f"🤖 *Powered by Groq (Llama 3.3) with Gemini fallback*"
        )

        keyboard = [
            [InlineKeyboardButton("📋 Get Briefing Now", callback_data="briefing_full")],
            [InlineKeyboardButton("📊 Markets", callback_data="markets"), InlineKeyboardButton("🌤️ Weather", callback_data="weather")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings"), InlineKeyboardButton("📈 Status", callback_data="status")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available commands and examples."""
        await update.message.reply_text(
            format_help(),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    # =========================================================================
    # BRIEFING COMMANDS
    # =========================================================================
    async def briefing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate or retrieve latest morning briefing."""
        # Check for mode argument
        args = context.args
        mode = "full"

        if args and args[0] in ["compact", "full", "detailed"]:
            mode = args[0]

        # Send "generating" message
        status_msg = await update.message.reply_text(
            f"🔄 Generating {mode} briefing... Please wait.",
            parse_mode="Markdown",
        )

        try:
            # Generate briefing
            briefing = await self.engine.generate_briefing(mode=mode)

            if briefing.status.value == "failed":
                await status_msg.edit_text(
                    f"❌ Briefing generation failed: {briefing.error}",
                    parse_mode="Markdown",
                )
                return

            # Delete status message
            await status_msg.delete()

            # Send briefing in chunks
            formatted = format_briefing(briefing, mode)
            for i, chunk in enumerate(formatted):
                await update.message.reply_text(
                    chunk,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                if i < len(formatted) - 1:
                    import asyncio
                    await asyncio.sleep(0.5)

            # Save to history
            await self.repo.save_briefing(briefing)

        except Exception as e:
            logger.error(f"Briefing command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error generating briefing: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    async def briefing_compact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate compact briefing."""
        context.args = ["compact"]
        await self.briefing(update, context)

    # =========================================================================
    # MARKETS COMMAND
    # =========================================================================
    async def markets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show latest market indicators with source timestamps."""
        status_msg = await update.message.reply_text(
            "📊 Fetching market data...",
            parse_mode="Markdown",
        )

        try:
            market_data = await data_source_manager.get_all_market_data()
            await status_msg.edit_text(
                format_markets(market_data),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Markets command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error fetching markets: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # NEWS COMMAND
    # =========================================================================
    async def news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Retrieve and summarize most important current news."""
        args = context.args
        category = "all"

        if args:
            category = args[0].lower()

        status_msg = await update.message.reply_text(
            f"📰 Fetching {category} news...",
            parse_mode="Markdown",
        )

        try:
            if category == "ca" or category == "canada":
                news_items = await data_source_manager.get_canadian_news(15)
            elif category == "ma" or category == "morocco":
                news_items = await data_source_manager.get_morocco_news(10)
            elif category == "energy" or category == "oil":
                news_items = await data_source_manager.get_energy_news(10)
            elif category == "cb" or category == "central_bank":
                news_items = await data_source_manager.get_central_bank_news(10)
            elif category == "housing" or category == "mortgage":
                news_items = await data_source_manager.get_housing_mortgage_news(8)
            elif category == "econ" or category == "economic":
                news_items = await data_source_manager.get_economic_indicators_news(8)
            else:
                news_items = await data_source_manager.get_top_news(20)

            await status_msg.edit_text(
                format_news(news_items, category),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"News command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error fetching news: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # WEATHER COMMAND
    # =========================================================================
    async def weather(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current weather and forecast."""
        args = context.args
        location = "montreal"

        if args and args[0].lower() in ["morocco", "casablanca", "ma"]:
            location = "morocco"

        status_msg = await update.message.reply_text(
            f"🌤️ Fetching weather for {location.title()}...",
            parse_mode="Markdown",
        )

        try:
            if location == "morocco":
                weather = await data_source_manager.get_morocco_weather()
            else:
                weather = await data_source_manager.get_weather()

            await status_msg.edit_text(
                format_weather(weather),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Weather command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error fetching weather: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # CALENDAR COMMAND
    # =========================================================================
    async def calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show economic calendar events."""
        args = context.args
        view = "week"

        if args and args[0] in ["today", "week", "cb", "central_bank"]:
            view = args[0]

        status_msg = await update.message.reply_text(
            f"📅 Fetching economic calendar ({view})...",
            parse_mode="Markdown",
        )

        try:
            if view == "today":
                events = await data_source_manager.get_today_calendar()
            elif view == "cb" or view == "central_bank":
                events = await data_source_manager.get_central_bank_events()
            else:
                events = await data_source_manager.get_week_calendar()

            await status_msg.edit_text(
                format_calendar(events, view),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Calendar command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error fetching calendar: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # MORTGAGE COMMAND
    # =========================================================================
    async def mortgage(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show mortgage analyst intelligence."""
        status_msg = await update.message.reply_text(
            "🏠 Fetching mortgage intelligence...",
            parse_mode="Markdown",
        )

        try:
            # Get data needed for mortgage section
            market_data = await data_source_manager.get_all_market_data()
            ca_economic = await data_source_manager.get_canadian_economic_data()
            us_economic = await data_source_manager.get_us_economic_data()

            # Generate briefing to get mortgage section
            briefing = await self.engine.generate_briefing(mode="full")
            mortgage_text = briefing.mortgage_intelligence or "Mortgage intelligence section not available."

            await status_msg.edit_text(
                format_mortgage(mortgage_text, market_data, ca_economic, us_economic),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Mortgage command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error fetching mortgage data: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # SAVINGS COMMAND
    # =========================================================================
    async def savings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show savings and personal finance updates."""
        status_msg = await update.message.reply_text(
            "💰 Fetching savings & personal finance data...",
            parse_mode="Markdown",
        )

        try:
            briefing = await self.engine.generate_briefing(mode="full")
            savings_text = briefing.savings_finance or "Savings & personal finance section not available."

            await status_msg.edit_text(
                format_savings(savings_text),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Savings command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error fetching savings data: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # SETTINGS COMMAND
    # =========================================================================
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View and change configurable preferences."""
        args = context.args

        if not args:
            # Show current settings
            user_settings = await self.repo.get_user_settings(self.auth.allowed_user_id)
            await update.message.reply_text(
                format_settings(user_settings),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            return

        # Handle settings changes
        setting = args[0].lower()

        if setting == "time" and len(args) >= 2:
            # Set delivery time: /settings time 09:00
            time_str = args[1]
            try:
                hour, minute = map(int, time_str.split(":"))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    await self.repo.update_user_setting(self.auth.allowed_user_id, "briefing_hour", hour)
                    await self.repo.update_user_setting(self.auth.allowed_user_id, "briefing_minute", minute)
                    await self.scheduler.reschedule_daily_briefing(hour, minute)
                    await update.message.reply_text(
                        f"✅ Delivery time updated to {hour:02d}:{minute:02d} {settings.timezone}",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text("❌ Invalid time. Use 24-hour format (0-23).")
            except ValueError:
                await update.message.reply_text("❌ Invalid format. Use HH:MM (e.g., 09:00).")

        elif setting == "timezone" and len(args) >= 2:
            # Set timezone: /settings timezone America/Montreal
            tz = args[1]
            try:
                import pytz
                pytz.timezone(tz)  # Validate
                await self.repo.update_user_setting(self.auth.allowed_user_id, "timezone", tz)
                await self.scheduler.reschedule_daily_briefing(
                    user_settings.briefing_hour if user_settings else settings.briefing_hour,
                    user_settings.briefing_minute if user_settings else settings.briefing_minute,
                )
                await update.message.reply_text(
                    f"✅ Timezone updated to {tz}",
                    parse_mode="Markdown",
                )
            except Exception:
                await update.message.reply_text("❌ Invalid timezone. Use IANA format (e.g., America/Toronto).")

        elif setting == "location" and len(args) >= 2:
            # Set weather location: /settings location Montreal
            city = " ".join(args[1:])
            await self.repo.update_user_setting(self.auth.allowed_user_id, "weather_city", city)
            await update.message.reply_text(
                f"✅ Weather location updated to {city}",
                parse_mode="Markdown",
            )

        elif setting == "language" and len(args) >= 2:
            # Set language: /settings language fr
            lang = args[1].lower()
            if lang in ["en", "fr", "ar"]:
                await self.repo.update_user_setting(self.auth.allowed_user_id, "default_language", lang)
                await update.message.reply_text(
                    f"✅ Language updated to {lang}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("❌ Supported languages: en, fr, ar")

        elif setting == "schedule" and len(args) >= 2:
            # Set schedule: /settings schedule daily or weekdays
            sched = args[1].lower()
            if sched in ["daily", "weekdays"]:
                weekdays_only = sched == "weekdays"
                await self.repo.update_user_setting(self.auth.allowed_user_id, "schedule_weekdays_only", weekdays_only)
                await self.scheduler.reschedule_daily_briefing(
                    user_settings.briefing_hour if user_settings else settings.briefing_hour,
                    user_settings.briefing_minute if user_settings else settings.briefing_minute,
                )
                await update.message.reply_text(
                    f"✅ Schedule updated to {sched}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("❌ Use 'daily' or 'weekdays'")

        elif setting == "mode" and len(args) >= 2:
            # Set briefing mode: /settings mode compact
            mode = args[1].lower()
            if mode in ["compact", "full", "detailed"]:
                await self.repo.update_user_setting(self.auth.allowed_user_id, "briefing_mode", mode)
                await update.message.reply_text(
                    f"✅ Briefing mode updated to {mode}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("❌ Use 'compact', 'full', or 'detailed'")

        else:
            await update.message.reply_text(
                "❌ Unknown setting. Use `/settings` to see current values.\n\n"
                "Available settings:\n"
                "• `/settings time HH:MM` — Delivery time (24hr)\n"
                "• `/settings timezone IANA_TZ` — e.g., America/Toronto\n"
                "• `/settings location City` — Weather location\n"
                "• `/settings language en|fr|ar`\n"
                "• `/settings schedule daily|weekdays`\n"
                "• `/settings mode compact|full|detailed`",
                parse_mode="Markdown",
            )

    # =========================================================================
    # STATUS COMMAND
    # =========================================================================
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inspect latest run, data freshness, next scheduled briefing, and errors."""
        status_msg = await update.message.reply_text(
            "📊 Checking system status...",
            parse_mode="Markdown",
        )

        try:
            # Get health checks
            health = await data_source_manager.health_check_all()

            # Get next scheduled run
            next_run = await self.scheduler.get_next_run()

            # Get last briefing status
            last_briefing = await self.repo.get_latest_briefing()

            # Get scheduler status
            scheduler_status = self.scheduler.get_status()

            await status_msg.edit_text(
                format_status(health, next_run, last_briefing, scheduler_status),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Status command failed: {e}")
            await status_msg.edit_text(
                f"❌ Error checking status: {str(e)[:200]}",
                parse_mode="Markdown",
            )

    # =========================================================================
    # CALLBACK HANDLER (Inline buttons)
    # =========================================================================
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "briefing_full":
            await query.edit_message_text("🔄 Generating full briefing...")
            # Create a fake update for the briefing command
            class FakeContext:
                args = ["full"]
            await self.briefing(query, FakeContext())

        elif data == "briefing_compact":
            await query.edit_message_text("🔄 Generating compact briefing...")
            class FakeContext:
                args = ["compact"]
            await self.briefing(query, FakeContext())

        elif data == "markets":
            await query.edit_message_text("📊 Fetching markets...")
            class FakeContext:
                args = []
            await self.markets(query, FakeContext())

        elif data == "weather":
            await query.edit_message_text("🌤️ Fetching weather...")
            class FakeContext:
                args = []
            await self.weather(query, FakeContext())

        elif data == "settings":
            await query.edit_message_text("⚙️ Loading settings...")
            class FakeContext:
                args = []
            await self.settings(query, FakeContext())

        elif data == "status":
            await query.edit_message_text("📊 Checking status...")
            class FakeContext:
                args = []
            await self.status(query, FakeContext())

        elif data.startswith("news_"):
            category = data.replace("news_", "")
            await query.edit_message_text(f"📰 Fetching {category} news...")
            class FakeContext:
                args = [category]
            await self.news(query, FakeContext())

        elif data.startswith("calendar_"):
            view = data.replace("calendar_", "")
            await query.edit_message_text(f"📅 Fetching calendar ({view})...")
            class FakeContext:
                args = [view]
            await self.calendar(query, FakeContext())

        else:
            await query.edit_message_text(f"Unknown action: {data}")