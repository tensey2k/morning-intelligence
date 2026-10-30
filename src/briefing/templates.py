"""
Briefing templates for Morning Intelligence Assistant.
Defines the structure and format for each briefing section.
"""
from datetime import date, datetime
from typing import Dict, Any, List
from src.config import settings


class BriefingTemplates:
    """Templates for generating morning briefings."""

    # Main template structure for LLM synthesis
    MASTER_TEMPLATE = {
        "executive_summary": {
            "description": "60-second executive summary with greeting, 3-5 major developments, biggest financial story, Canadian mortgage/savings impact, main risk/opportunity, daily status (calm/watchful/high-impact)",
            "max_length": 800,
        },
        "weather_daily_life": {
            "description": "Weather for Montreal (and optionally Casablanca): current temp, feels-like, high/low, rain/snow probability, wind, alerts, practical commuting/clothing advice",
            "max_length": 400,
        },
        "markets_dashboard": {
            "description": "Oil (Brent/WTI with changes), Crypto (BTC/ETH USD/CAD), Canadian rates (BoC policy, 2Y/5Y/10Y yields, prime, mortgage indicators, savings/GIC), US rates (Fed, 2Y/10Y Treasuries), Stock indices (S&P500, Nasdaq, DJI, TSX, Euro Stoxx 50, CAC 40, FTSE 100, Nikkei, Hang Seng), FX (USD/CAD, EUR/CAD, MAD/CAD, EUR/USD, USD/MAD). Include price, currency, units, timestamp, data freshness.",
            "max_length": 1200,
        },
        "major_global_news": {
            "description": "5-8 high-impact stories ranked by importance. Priority: CA economic/housing/political, US monetary/fiscal, geopolitical, EU monetary, Morocco economic. Each: headline, factual summary, why it matters, relevance to work/CA/MA, publication time, clickable source.",
            "max_length": 1500,
        },
        "essential_news_daily_life": {
            "description": "Consequential practical info: CA weather emergencies/transport, tax deadlines/benefits/housing rules, fraud/cybersecurity, health/safety alerts, travel advisories (CA/MA), major tech/service changes. Say explicitly if no significant alerts.",
            "max_length": 600,
        },
        "mortgage_analyst_intelligence": {
            "description": "Changes in CA 2Y/5Y bond yields, implications for fixed mortgage rates, BoC expectations/variable rates, new CPI/employment/GDP/housing data, mortgage renewals/affordability/arrears, savings products/GICs/household borrowing costs, upcoming releases/central bank decisions. Distinguish facts from interpretation/forecasts.",
            "max_length": 800,
        },
        "savings_personal_finance": {
            "description": "TFSA/RRSP/FHSA/RESP rule changes, interest rates/inflation/savings accounts/GICs, CA tax developments/contribution limits, consumer banking/deposit protection/fraud prevention, practical financial literacy. Use official sources. No individualized advice.",
            "max_length": 600,
        },
        "economic_calendar": {
            "description": "Verified events today and next 7 days: BoC/Fed announcements, CA/US inflation/employment/GDP/housing, Treasury auctions, OPEC+ meetings, oil inventories, policy announcements. Use local timezone. No invented events.",
            "max_length": 600,
        },
        "three_priorities": {
            "description": "Exactly three items: 1) Market watch (key indicator/event), 2) Professional watch (mortgage/savings/macro development), 3) Personal watch (practical alert/risk/opportunity).",
            "max_length": 400,
        },
    }

    # Compact template for short briefings
    COMPACT_TEMPLATE = {
        "executive_summary": MASTER_TEMPLATE["executive_summary"],
        "markets_dashboard": MASTER_TEMPLATE["markets_dashboard"],
        "major_global_news": MASTER_TEMPLATE["major_global_news"],
        "three_priorities": MASTER_TEMPLATE["three_priorities"],
    }

    # Detailed template for comprehensive briefings
    DETAILED_TEMPLATE = MASTER_TEMPLATE

    @classmethod
    def get_template(cls, mode: str = None) -> Dict[str, Any]:
        """Get template for briefing mode."""
        if mode is None:
            mode = settings.briefing_mode

        templates = {
            "compact": cls.COMPACT_TEMPLATE,
            "full": cls.MASTER_TEMPLATE,
            "detailed": cls.DETAILED_TEMPLATE,
        }
        return templates.get(mode, cls.MASTER_TEMPLATE)

    @classmethod
    def get_system_prompt(cls, mode: str = None, language: str = "en") -> str:
        """Get system prompt for LLM briefing synthesis."""
        template = cls.get_template(mode)

        lang_instructions = {
            "en": "Write in professional English.",
            "fr": "Rédigez en français professionnel.",
            "ar": "اكتب باللغة العربية المهنية.",
        }

        sections = "\n".join([
            f"- {key}: {info['description']} (max ~{info['max_length']} chars)"
            for key, info in template.items()
        ])

        return f"""You are a senior financial analyst and macroeconomic researcher creating a morning intelligence briefing for a Moroccan-Canadian financial analyst focused on mortgages, savings, interest rates, and financial products.

Target audience: Busy professional in Canada (Montreal timezone), interested in global macroeconomics, oil, Bitcoin, financial markets, geopolitics, Canadian housing, and personal finance. Covers Canada, US, Morocco, Europe.

{lang_instructions.get(language, lang_instructions["en"])}

BRIEFING STRUCTURE (follow exactly):
{sections}

FORMATTING RULES:
- Use clear section headings with emoji indicators
- Concise paragraphs, bullet points for readability
- Consistent currency formatting: $X.XX CAD, $X.XX USD, €X.XX, MAD X.XX
- Percentages: X.XX% (2 decimals for rates, 1 for changes)
- Explicit timestamps: "As of 2024-01-15 06:30 EST" or "Delayed (EOD 2024-01-14)"
- Source references: [Source: Bank of Canada], [Source: Alpha Vantage], [Source: Reuters]
- Flag stale data: "⚠️ Data delayed by X hours"
- Mobile-optimized: short lines, clear hierarchy

CONTENT RULES:
- Distinguish verified facts from interpretation/forecasts
- Never invent prices, rates, or events
- If data missing: "Data unavailable: [reason]"
- No individualized financial/tax/legal advice
- Professional tone, actionable intelligence
- 5-8 minute read for full briefing, 60 seconds for executive summary

DATE CONTEXT: Briefing for {date.today().strftime('%A, %B %d, %Y')} in {settings.timezone}"""

    @classmethod
    def format_briefing_markdown(cls, briefing: Dict[str, Any], mode: str = None) -> str:
        """Format briefing dict as Markdown for Telegram."""
        template = cls.get_template(mode)
        lines = []

        # Header
        lines.append(f"🌅 **Morning Intelligence Briefing**")
        lines.append(f"📅 {date.today().strftime('%A, %B %d, %Y')} | 🕕 {datetime.now().strftime('%H:%M')} {settings.timezone}")
        lines.append("")

        # Executive Summary
        if "executive_summary" in briefing:
            lines.append("📋 **EXECUTIVE SUMMARY** (60-sec read)")
            lines.append(briefing["executive_summary"])
            lines.append("")

        # Weather
        if "weather_daily_life" in briefing and briefing.get("weather_daily_life"):
            lines.append("🌤️ **WEATHER & DAILY LIFE**")
            lines.append(briefing["weather_daily_life"])
            lines.append("")

        # Markets
        if "markets_dashboard" in briefing:
            lines.append("📈 **MARKETS DASHBOARD**")
            lines.append(briefing["markets_dashboard"])
            lines.append("")

        # Major News
        if "major_global_news" in briefing:
            lines.append("🌍 **MAJOR GLOBAL NEWS**")
            lines.append(briefing["major_global_news"])
            lines.append("")

        # Essential News
        if "essential_news_daily_life" in briefing and briefing.get("essential_news_daily_life"):
            lines.append("📍 **ESSENTIAL NEWS FOR DAILY LIFE**")
            lines.append(briefing["essential_news_daily_life"])
            lines.append("")

        # Mortgage Intelligence
        if "mortgage_analyst_intelligence" in briefing and briefing.get("mortgage_analyst_intelligence"):
            lines.append("🏠 **MORTGAGE ANALYST INTELLIGENCE**")
            lines.append(briefing["mortgage_analyst_intelligence"])
            lines.append("")

        # Savings & Personal Finance
        if "savings_personal_finance" in briefing and briefing.get("savings_personal_finance"):
            lines.append("💰 **SAVINGS & PERSONAL FINANCE**")
            lines.append(briefing["savings_personal_finance"])
            lines.append("")

        # Economic Calendar
        if "economic_calendar" in briefing and briefing.get("economic_calendar"):
            lines.append("📅 **ECONOMIC CALENDAR (Next 7 Days)**")
            lines.append(briefing["economic_calendar"])
            lines.append("")

        # Three Priorities
        if "three_priorities" in briefing:
            lines.append("🎯 **THREE PRIORITIES FOR TODAY**")
            lines.append(briefing["three_priorities"])
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Generated by Morning Intelligence Assistant | Data as of {datetime.now().strftime('%H:%M %Z')}*")
        lines.append(f"*Sources: Bank of Canada, Alpha Vantage, CoinGecko, Open-Meteo, FinanceCalendar, RSS feeds*")
        lines.append(f"*⚠️ Not financial advice. Verify before acting.*")

        return "\n".join(lines)

    @classmethod
    def split_message(cls, text: str, max_length: int = 4096) -> List[str]:
        """Split long message into chunks respecting section boundaries."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""
        sections = text.split("\n\n")

        for section in sections:
            if len(current_chunk) + len(section) + 2 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = section
            else:
                if current_chunk:
                    current_chunk += "\n\n" + section
                else:
                    current_chunk = section

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks