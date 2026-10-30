"""
Briefing Engine - orchestrates data collection, LLM synthesis, and formatting.
"""
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.config import settings
from src.data_sources.manager import data_source_manager
from src.briefing.llm_client import llm_client
from src.briefing.templates import BriefingTemplates
from src.models import BriefingStatus, MorningBriefing, WeatherData


class BriefingEngine:
    """Main briefing generation engine."""

    def __init__(self):
        self.templates = BriefingTemplates()
        self.llm = llm_client
        self.data_sources = data_source_manager

    async def generate_briefing(
        self,
        briefing_date: date = None,
        mode: str = None,
        language: str = None,
        force_refresh: bool = False,
    ) -> MorningBriefing:
        """Generate a complete morning briefing."""
        if briefing_date is None:
            briefing_date = date.today()
        if mode is None:
            mode = settings.briefing_mode
        if language is None:
            language = settings.default_language

        briefing = MorningBriefing(
            id=uuid4(),
            briefing_date=briefing_date,
            timezone=settings.timezone,
            language=language,
            mode=mode,
            status=BriefingStatus.GENERATING,
        )

        try:
            # Collect all raw data
            raw_data = await self.data_sources.collect_briefing_data()

            # Synthesize with LLM
            synthesized = await self._synthesize_briefing(raw_data, mode, language)

            # Populate briefing object
            briefing = self._populate_briefing(briefing, synthesized, raw_data)

            # Format for delivery
            briefing.formatted_markdown = self.templates.format_briefing_markdown(synthesized, mode)
            briefing.formatted_chunks = self.templates.split_message(
                briefing.formatted_markdown, settings.max_message_length
            )

            briefing.status = BriefingStatus.GENERATED
            return briefing

        except Exception as e:
            briefing.status = BriefingStatus.FAILED
            briefing.error = str(e)
            return briefing

    async def _synthesize_briefing(
        self,
        raw_data: Dict[str, Any],
        mode: str,
        language: str,
    ) -> Dict[str, Any]:
        """Use LLM to synthesize raw data into structured briefing."""
        template = self.templates.get_template(mode)
        system_prompt = self.templates.get_system_prompt(mode, language)

        # Prepare structured data for LLM
        llm_input = self._prepare_llm_input(raw_data)

        # Synthesize
        response = await self.llm.structure_briefing(llm_input, json.dumps(template, indent=2))

        return response

    def _prepare_llm_input(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare raw data for LLM consumption."""
        market = raw_data.get("market_data", {})
        weather = raw_data.get("weather")
        morocco_weather = raw_data.get("morocco_weather")
        news = raw_data.get("news", [])
        calendar = raw_data.get("calendar", [])
        ca_economic = raw_data.get("canadian_economic", {})

        return {
            "date": date.today().isoformat(),
            "timezone": settings.timezone,
            "market_data": {
                "oil": [self._serialize_market_item(o) for o in market.get("oil", [])],
                "crypto": [self._serialize_market_item(c) for c in market.get("crypto", [])],
                "bonds": [self._serialize_market_item(b) for b in market.get("bonds", [])],
                "policy_rates": [self._serialize_market_item(r) for r in market.get("policy_rates", [])],
                "indices": [self._serialize_market_item(i) for i in market.get("indices", [])],
                "forex": [self._serialize_market_item(f) for f in market.get("forex", [])],
            },
            "weather": self._serialize_weather(weather) if weather else None,
            "morocco_weather": self._serialize_weather(morocco_weather) if morocco_weather else None,
            "news": [self._serialize_news(n) for n in news[:20]],
            "calendar": [self._serialize_calendar(c) for c in calendar[:30]],
            "canadian_economic": {
                "bond_yields": [self._serialize_market_item(b) for b in ca_economic.get("bond_yields", [])],
                "policy_rate": self._serialize_market_item(ca_economic.get("policy_rate")) if ca_economic.get("policy_rate") else None,
                "money_market": [self._serialize_market_item(m) for m in ca_economic.get("money_market", [])],
                "exchange_rates": [self._serialize_market_item(e) for e in ca_economic.get("exchange_rates", [])],
                "cpi": self._serialize_market_item(ca_economic.get("cpi")) if ca_economic.get("cpi") else None,
            },
            "errors": raw_data.get("collection_errors", []),
        }

    def _serialize_market_item(self, item: Any) -> Dict[str, Any]:
        """Serialize market data item for LLM."""
        if item is None:
            return {}
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        return {"error": "Unable to serialize"}

    def _serialize_weather(self, weather: WeatherData) -> Dict[str, Any]:
        """Serialize weather data for LLM."""
        if weather is None:
            return {}
        return {
            "city": weather.city,
            "country": weather.country,
            "current_temp_c": float(weather.current_temp_c) if weather.current_temp_c else None,
            "feels_like_c": float(weather.feels_like_c) if weather.feels_like_c else None,
            "high_temp_c": float(weather.high_temp_c) if weather.high_temp_c else None,
            "low_temp_c": float(weather.low_temp_c) if weather.low_temp_c else None,
            "wind_speed_kmh": float(weather.wind_speed_kmh) if weather.wind_speed_kmh else None,
            "wind_direction": weather.wind_direction,
            "precipitation_probability_pct": weather.precipitation_probability_pct,
            "precipitation_mm": float(weather.precipitation_mm) if weather.precipitation_mm else None,
            "snow_probability_pct": weather.snow_probability_pct,
            "weather_description": weather.weather_description,
            "alerts": weather.alerts,
            "forecast_daily": weather.forecast_daily,
            "timestamp": weather.timestamp.isoformat() if weather.timestamp else None,
        }

    def _serialize_news(self, news: Any) -> Dict[str, Any]:
        """Serialize news item for LLM."""
        if news is None:
            return {}
        if hasattr(news, "model_dump"):
            return news.model_dump(mode="json")
        return {"error": "Unable to serialize"}

    def _serialize_calendar(self, event: Any) -> Dict[str, Any]:
        """Serialize calendar event for LLM."""
        if event is None:
            return {}
        if hasattr(event, "model_dump"):
            return event.model_dump(mode="json")
        return {"error": "Unable to serialize"}

    def _populate_briefing(
        self,
        briefing: MorningBriefing,
        synthesized: Dict[str, Any],
        raw_data: Dict[str, Any],
    ) -> MorningBriefing:
        """Populate briefing object with synthesized content."""
        briefing.executive_summary = synthesized.get("executive_summary")
        briefing.weather = raw_data.get("weather")
        briefing.morocco_weather = raw_data.get("morocco_weather")
        briefing.markets = raw_data.get("market_data", {})
        briefing.news = raw_data.get("news", [])
        briefing.essential_news = [n for n in raw_data.get("news", []) if n.category in ["emergency", "alert", "consumer"]]
        briefing.mortgage_intelligence = synthesized.get("mortgage_analyst_intelligence")
        briefing.savings_finance = synthesized.get("savings_personal_finance")
        briefing.economic_calendar = raw_data.get("calendar", [])
        briefing.priorities = synthesized.get("three_priorities", [])

        # Ensure exactly 3 priorities
        if isinstance(briefing.priorities, list) and len(briefing.priorities) > 3:
            briefing.priorities = briefing.priorities[:3]
        elif isinstance(briefing.priorities, str):
            # Parse from string if needed
            lines = [l.strip() for l in briefing.priorities.split("\n") if l.strip()]
            briefing.priorities = lines[:3]

        return briefing

    async def generate_compact_briefing(self, briefing_date: date = None) -> MorningBriefing:
        """Generate compact briefing (executive summary + markets + top news + priorities)."""
        return await self.generate_briefing(briefing_date, mode="compact")

    async def generate_full_briefing(self, briefing_date: date = None) -> MorningBriefing:
        """Generate full briefing (all sections)."""
        return await self.generate_briefing(briefing_date, mode="full")

    async def generate_detailed_briefing(self, briefing_date: date = None) -> MorningBriefing:
        """Generate detailed briefing (all sections with extra detail)."""
        return await self.generate_briefing(briefing_date, mode="detailed")

    async def close(self):
        """Close all connections."""
        await self.data_sources.close_all()
        await self.llm.close()


# Global instance
briefing_engine = BriefingEngine()