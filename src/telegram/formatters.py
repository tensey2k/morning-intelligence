"""
Telegram message formatters for Morning Intelligence Assistant.
Formats briefing sections, markets, weather, news, status, etc. for Telegram delivery.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.models import (
    BondYield,
    CalendarEvent,
    CryptoPrice,
    ForexRate,
    MarketDataPoint,
    MorningBriefing,
    NewsItem,
    OilPrice,
    StockIndex,
    WeatherData,
)


def format_briefing(briefing: MorningBriefing, mode: str = "full") -> List[str]:
    """Format complete briefing for Telegram delivery."""
    return briefing.formatted_chunks if briefing.formatted_chunks else []


def format_markets(market_data: Dict[str, Any]) -> str:
    """Format market data for Telegram."""
    lines = ["📈 **MARKETS DASHBOARD**", ""]

    # Oil
    oil = market_data.get("oil", [])
    if oil:
        lines.append("🛢️ **OIL**")
        for o in oil:
            benchmark = o.benchmark if hasattr(o, 'benchmark') else o.metadata.get("benchmark", "UNKNOWN")
            price = o.price_per_barrel if hasattr(o, 'price_per_barrel') else o.value
            change = o.change_24h_pct if hasattr(o, 'change_24h_pct') else None
            delayed = " ⚠️ Delayed" if (hasattr(o, 'is_delayed') and o.is_delayed) else ""
            lines.append(f"  • {benchmark}: ${price:.2f}/bbl{delayed}")
            if change:
                lines.append(f"    24h: {change:+.2f}%")
        lines.append("")

    # Crypto
    crypto = market_data.get("crypto", [])
    if crypto:
        lines.append("₿ **CRYPTOCURRENCY**")
        for c in crypto:
            symbol = c.symbol if hasattr(c, 'symbol') else "UNKNOWN"
            price_usd = c.price_usd if hasattr(c, 'price_usd') else c.value
            price_cad = c.price_cad if hasattr(c, 'price_cad') else None
            change = c.change_24h_pct if hasattr(c, 'change_24h_pct') else None
            lines.append(f"  • {symbol}: ${price_usd:,.0f} USD" + (f" / C${price_cad:,.0f} CAD" if price_cad else "") + (f" ({change:+.2f}%)" if change else ""))
        lines.append("")

    # Bonds
    bonds = market_data.get("bonds", [])
    if bonds:
        lines.append("🏛️ **BOND YIELDS**")
        ca_bonds = [b for b in bonds if (hasattr(b, 'country') and b.country == "CA") or (hasattr(b, 'metadata') and b.metadata.get("country") == "CA")]
        us_bonds = [b for b in bonds if (hasattr(b, 'country') and b.country == "US") or (hasattr(b, 'metadata') and b.metadata.get("country") == "US")]

        if ca_bonds:
            lines.append("  **Canada:**")
            for b in sorted(ca_bonds, key=lambda x: x.maturity_years if hasattr(x, 'maturity_years') else 0):
                maturity = b.maturity_years if hasattr(b, 'maturity_years') else 0
                yield_pct = b.yield_pct if hasattr(b, 'yield_pct') else b.value
                label = "Policy Rate" if maturity == 0 else f"{maturity}Y"
                lines.append(f"    • {label}: {yield_pct:.2f}%")
        if us_bonds:
            lines.append("  **US:**")
            for b in sorted(us_bonds, key=lambda x: x.maturity_years if hasattr(x, 'maturity_years') else 0):
                maturity = b.maturity_years if hasattr(b, 'maturity_years') else 0
                yield_pct = b.yield_pct if hasattr(b, 'yield_pct') else b.value
                label = "Fed Funds" if maturity == 0 else f"{maturity}Y"
                lines.append(f"    • {label}: {yield_pct:.2f}%")
        lines.append("")

    # Yield Spreads
    spreads = market_data.get("yield_spreads", [])
    if spreads:
        lines.append("📊 **YIELD SPREADS**")
        for s in spreads:
            desc = s.metadata.get("spread", "Spread") if hasattr(s, 'metadata') else "Spread"
            lines.append(f"  • {desc}: {s.value:.2f}%")
        lines.append("")

    # Policy Rates
    policy = market_data.get("policy_rates", [])
    if policy:
        lines.append("🏦 **POLICY RATES**")
        for p in policy:
            country = p.country if hasattr(p, 'country') else "Unknown"
            rate = p.yield_pct if hasattr(p, 'yield_pct') else p.value
            typ = p.metadata.get("type", "Policy Rate") if hasattr(p, 'metadata') else "Policy Rate"
            lines.append(f"  • {country} {typ}: {rate:.2f}%")
        lines.append("")

    # Stock Indices
    indices = market_data.get("indices", [])
    if indices:
        lines.append("📊 **STOCK INDICES**")
        major = ["S&P 500", "Nasdaq", "Dow Jones", "S&P/TSX", "Euro Stoxx 50", "CAC 40", "FTSE 100", "Nikkei 225", "Hang Seng"]
        for idx in indices:
            name = idx.index_name if hasattr(idx, 'index_name') else "Unknown"
            if any(m in name for m in major):
                val = idx.index_value if hasattr(idx, 'index_value') else idx.value
                lines.append(f"  • {name}: {val:,.0f}")
        lines.append("")

    # Forex
    forex = market_data.get("forex", [])
    if forex:
        lines.append("💱 **FOREX**")
        key_pairs = ["USD/CAD", "EUR/CAD", "USD/MAD", "EUR/USD", "GBP/CAD"]
        for f in forex:
            unit = f.unit if hasattr(f, 'unit') else ""
            if any(p in unit for p in key_pairs):
                rate = f.rate if hasattr(f, 'rate') else f.value
                lines.append(f"  • {unit}: {rate:.4f}")
        lines.append("")

    # Errors
    errors = market_data.get("errors", [])
    if errors:
        lines.append("⚠️ **ERRORS**")
        for e in errors:
            lines.append(f"  • {e}")

    lines.append(f"*Data as of {datetime.now().strftime('%H:%M %Z')} | Sources: BoC, FRED, EIA, Alpha Vantage, CoinGecko*")
    return "\n".join(lines)


def format_weather(weather: WeatherData) -> str:
    """Format weather data for Telegram."""
    if not weather:
        return "❌ Weather data unavailable"

    lines = [f"🌤️ **WEATHER - {weather.city}, {weather.country}**", ""]

    if weather.current_temp_c is not None:
        lines.append(f"🌡️ Current: {weather.current_temp_c:.1f}°C")
    if weather.feels_like_c is not None:
        lines.append(f"🤗 Feels like: {weather.feels_like_c:.1f}°C")
    if weather.high_temp_c is not None and weather.low_temp_c is not None:
        lines.append(f"📊 Today: {weather.high_temp_c:.1f}°C / {weather.low_temp_c:.1f}°C")
    if weather.precipitation_probability_pct is not None:
        lines.append(f"🌧️ Rain: {weather.precipitation_probability_pct}%")
    if weather.snow_probability_pct is not None and weather.snow_probability_pct > 0:
        lines.append(f"❄️ Snow: {weather.snow_probability_pct}%")
    if weather.wind_speed_kmh is not None:
        dir_str = f" {weather.wind_direction}" if weather.wind_direction else ""
        lines.append(f"💨 Wind: {weather.wind_speed_kmh:.0f} km/h{dir_str}")
    if weather.weather_description:
        lines.append(f"☁️ {weather.weather_description}")

    if weather.alerts:
        lines.append("")
        lines.append("⚠️ **ALERTS:**")
        for alert in weather.alerts:
            lines.append(f"  • {alert}")

    if weather.forecast_daily:
        lines.append("")
        lines.append("📅 **3-DAY FORECAST:**")
        for day in weather.forecast_daily[:3]:
            date_str = day.get("date", "")
            high = day.get("high_temp_c")
            low = day.get("low_temp_c")
            precip = day.get("precip_probability_pct")
            desc = day.get("weather_description", "")
            lines.append(f"  • {date_str}: {high:.1f}°/{low:.1f}°C | 🌧️ {precip}% | {desc}")

    lines.append("")
    lines.append(f"*Source: Open-Meteo | Updated {datetime.now().strftime('%H:%M %Z')}*")
    return "\n".join(lines)


def format_news(news_items: List[NewsItem], category: str = "all") -> str:
    """Format news items for Telegram."""
    if not news_items:
        return f"📰 No {category} news available at this time."

    lines = [f"📰 **TOP NEWS ({category.upper()})**", ""]

    for i, item in enumerate(news_items[:10], 1):
        # Format date
        pub_time = item.published_at.strftime("%H:%M UTC") if item.published_at else "Unknown time"

        # Region emoji
        region_emoji = ""
        if "CA" in item.regions:
            region_emoji = "🇨🇦 "
        elif "US" in item.regions:
            region_emoji = "🇺🇸 "
        elif "MA" in item.regions:
            region_emoji = "🇲🇦 "
        elif "EU" in item.regions or "GB" in item.regions:
            region_emoji = "🇪🇺 "

        lines.append(f"{i}. {region_emoji}**{item.headline}**")
        if item.summary:
            lines.append(f"   {item.summary[:300]}")
        lines.append(f"   📅 {pub_time} | 🔗 [Read more]({item.url})")
        if item.category:
            lines.append(f"   🏷️ {item.category}")
        lines.append("")

    lines.append(f"*{len(news_items)} articles | Sources: RSS + MarketAux*")
    return "\n".join(lines)


def format_status(
    health: Dict[str, bool],
    next_run: Optional[datetime],
    last_briefing: Optional[Any],
    scheduler_status: Dict[str, Any]
) -> str:
    """Format system status for Telegram."""
    lines = ["📊 **SYSTEM STATUS**", ""]

    # Data source health
    lines.append("🔌 **DATA SOURCES:**")
    for source, healthy in health.items():
        status = "✅" if healthy else "❌"
        lines.append(f"  {status} {source}")
    lines.append("")

    # Scheduler status
    lines.append("⏰ **SCHEDULER:**")
    lines.append(f"  • Running: {'✅' if scheduler_status.get('running') else '❌'}")
    lines.append(f"  • Next run: {next_run.strftime('%Y-%m-%d %H:%M %Z') if next_run else 'Not scheduled'}")
    lines.append(f"  • Timezone: {scheduler_status.get('timezone', 'Unknown')}")
    lines.append("")

    # Last briefing
    lines.append("📋 **LAST BRIEFING:**")
    if last_briefing:
        lines.append(f"  • Date: {last_briefing.date if hasattr(last_briefing, 'date') else 'Unknown'}")
        lines.append(f"  • Status: {last_briefing.status if hasattr(last_briefing, 'status') else 'Unknown'}")
        lines.append(f"  • Generated: {last_briefing.generated_at.strftime('%H:%M UTC') if hasattr(last_briefing, 'generated_at') and last_briefing.generated_at else 'Unknown'}")
    else:
        lines.append("  • No briefing generated yet")
    lines.append("")

    # System info
    lines.append("🖥️ **SYSTEM:**")
    lines.append(f"  • Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append(f"  • Uptime: {scheduler_status.get('uptime', 'Unknown')}")

    return "\n".join(lines)


def format_help() -> str:
    """Format help message."""
    return (
        "📖 **MORNING INTELLIGENCE - HELP**\n\n"
        "**Commands:**\n"
        "• `/start` — Welcome & quick start\n"
        "• `/help` — This message\n"
        "• `/briefing [compact|full|detailed]` — Get morning briefing\n"
        "• `/markets` — Current market indicators\n"
        "• `/news [ca|us|ma|energy|cb|housing|econ]` — Financial news\n"
        "• `/weather [montreal|morocco]` — Weather forecast\n"
        "• `/calendar [today|week|cb]` — Economic calendar\n"
        "• `/mortgage` — Mortgage analyst intelligence\n"
        "• `/savings` — Savings & personal finance\n"
        "• `/settings` — View current settings\n"
        "• `/settings time HH:MM` — Set delivery time (24hr)\n"
        "• `/settings timezone IANA_TZ` — Set timezone\n"
        "• `/settings location City` — Set weather location\n"
        "• `/settings language en|fr|ar`\n"
        "• `/settings schedule daily|weekdays`\n"
        "• `/settings mode compact|full|detailed`\n"
        "• `/status` — System health & next run\n\n"
        "**Quick Actions:**\n"
        "Use inline buttons from `/start` for one-tap access.\n\n"
        "**Data Sources:**\n"
        "Bank of Canada, FRED, EIA, Alpha Vantage, CoinGecko, Open-Meteo, MarketAux, RSS feeds\n\n"
        "**LLM:** Groq (Llama 3.3) → Gemini → OpenRouter → Cloudflare"
    )


def format_settings(user_settings: Optional[Any]) -> str:
    """Format user settings for Telegram."""
    lines = ["⚙️ **CURRENT SETTINGS**", ""]

    if user_settings:
        lines.append(f"🕐 Delivery: {user_settings.briefing_hour:02d}:{user_settings.briefing_minute:02d} {user_settings.timezone}")
        lines.append(f"📅 Schedule: {'Weekdays only' if user_settings.schedule_weekdays_only else 'Daily'}")
        lines.append(f"🌤️ Weather: {user_settings.weather_city}, {user_settings.weather_country}")
        lines.append(f"🌍 Language: {user_settings.default_language}")
        lines.append(f"📋 Mode: {user_settings.briefing_mode}")
    else:
        from src.config import settings
        lines.append(f"🕐 Delivery: {settings.briefing_hour:02d}:{settings.briefing_minute:02d} {settings.timezone}")
        lines.append(f"📅 Schedule: {'Weekdays only' if settings.schedule_weekdays_only else 'Daily'}")
        lines.append(f"🌤️ Weather: {settings.weather_city}, {settings.weather_country}")
        lines.append(f"🌍 Language: {settings.default_language}")
        lines.append(f"📋 Mode: {settings.briefing_mode}")
        lines.append("")
        lines.append("*Using defaults (not yet saved to database)*")

    lines.append("")
    lines.append("**Change settings:**")
    lines.append("• `/settings time 09:00`")
    lines.append("• `/settings timezone America/Montreal`")
    lines.append("• `/settings location Montreal`")
    lines.append("• `/settings language fr`")
    lines.append("• `/settings schedule weekdays`")
    lines.append("• `/settings mode compact`")

    return "\n".join(lines)


def format_calendar(events: List[CalendarEvent], view: str = "week") -> str:
    """Format economic calendar for Telegram."""
    if not events:
        return f"📅 No economic events for {view}."

    lines = [f"📅 **ECONOMIC CALENDAR ({view.upper()})**", ""]

    current_date = None
    for event in events[:25]:
        if event.date != current_date:
            current_date = event.date
            lines.append(f"\n📆 **{current_date.strftime('%A, %B %d')}**")

        time_str = f" {event.time}" if event.time else ""
        importance_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.importance, "⚪")

        lines.append(f"  {importance_emoji} {event.event_name} ({event.country}){time_str}")
        if event.forecast:
            lines.append(f"     Forecast: {event.forecast} | Previous: {event.previous or 'N/A'}")
        if event.actual:
            lines.append(f"     ✅ Actual: {event.actual}")

    lines.append("")
    lines.append(f"*{len(events)} events | Source: FinanceCalendar*")
    return "\n".join(lines)


def format_mortgage(mortgage_text: str, market_data: Dict, ca_economic: Dict, us_economic: Dict) -> str:
    """Format mortgage intelligence section."""
    lines = ["🏠 **MORTGAGE ANALYST INTELLIGENCE**", ""]

    # Key rates summary
    bonds = market_data.get("bonds", [])
    ca_bonds = [b for b in bonds if (hasattr(b, 'country') and b.country == "CA") or (hasattr(b, 'metadata') and b.metadata.get("country") == "CA")]

    if ca_bonds:
        lines.append("**Key Canadian Rates:**")
        for b in sorted(ca_bonds, key=lambda x: x.maturity_years if hasattr(x, 'maturity_years') else 0):
            mat = b.maturity_years if hasattr(b, 'maturity_years') else 0
            yld = b.yield_pct if hasattr(b, 'yield_pct') else b.value
            label = "Policy" if mat == 0 else f"{mat}Y"
            lines.append(f"  • {label}: {yld:.2f}%")
        lines.append("")

    lines.append(mortgage_text)
    lines.append("")
    lines.append("*Not financial advice. Verify with your mortgage broker.*")
    return "\n".join(lines)


def format_savings(savings_text: str) -> str:
    """Format savings & personal finance section."""
    lines = ["💰 **SAVINGS & PERSONAL FINANCE**", ""]
    lines.append(savings_text)
    lines.append("")
    lines.append("*Not financial advice. Consult a qualified advisor for personalized guidance.*")
    return "\n".join(lines)