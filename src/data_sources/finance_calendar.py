"""
FinanceCalendar.com API source for economic calendar events.
Free tier: 2,000 requests/day keyless, 10,000 with free key.
Coverage: US, CA, GB, EU, DE (no Morocco).
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import CalendarEvent, DataSource


class FinanceCalendarSource(DataSourceBase):
    """FinanceCalendar.com economic calendar API client."""

    BASE_URL = "https://api.financecalendar.com/v1"

    # Country codes supported
    COUNTRIES = ["US", "CA", "GB", "EU", "DE", "FR", "JP", "CN", "AU", "CH"]

    def __init__(self):
        super().__init__(
            name="FinanceCalendar",
            base_url=self.BASE_URL,
            api_key=None,  # Keyless works for 2000/day
            timeout=30.0,
            max_retries=3,
        )

    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "MorningIntelligence/1.0",
            "Accept": "application/json",
        }

    async def health_check(self) -> bool:
        """Check API availability."""
        try:
            params = {"country": "US", "date_from": date.today().isoformat(), "date_to": date.today().isoformat()}
            await self._request("GET", "/calendar", params=params)
            return True
        except Exception:
            return False

    async def get_events(
        self,
        countries: List[str] = None,
        date_from: date = None,
        date_to: date = None,
        importance: List[str] = None,
    ) -> List[CalendarEvent]:
        """Get economic calendar events."""
        if countries is None:
            countries = ["US", "CA", "EU", "GB"]
        if date_from is None:
            date_from = date.today()
        if date_to is None:
            date_to = date.today() + timedelta(days=7)
        if importance is None:
            importance = ["high", "medium"]

        params = {
            "country": ",".join(countries),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "importance": ",".join(importance),
        }

        try:
            data = await self._request("GET", "/calendar", params=params)
            events = []

            for item in data.get("data", []):
                try:
                    event_date = datetime.fromisoformat(item.get("date", "")).date()
                    event_time = item.get("time")
                    timezone = item.get("timezone", "UTC")

                    events.append(CalendarEvent(
                        event_name=item.get("event", ""),
                        country=item.get("country", ""),
                        date=event_date,
                        time=event_time,
                        timezone=timezone,
                        actual=item.get("actual"),
                        forecast=item.get("forecast"),
                        previous=item.get("previous"),
                        importance=item.get("importance", "medium").lower(),
                        category=item.get("category", "economic"),
                        source=DataSource.FINANCE_CALENDAR,
                    ))
                except Exception:
                    continue

            return events

        except Exception as e:
            raise DataSourceError(f"Failed to fetch calendar events: {e}", self.name)

    async def get_today_events(self, countries: List[str] = None) -> List[CalendarEvent]:
        """Get today's economic events."""
        return await self.get_events(countries=countries, date_from=date.today(), date_to=date.today())

    async def get_week_events(self, countries: List[str] = None) -> List[CalendarEvent]:
        """Get this week's economic events."""
        return await self.get_events(countries=countries, date_from=date.today(), date_to=date.today() + timedelta(days=7))

    async def get_central_bank_events(self) -> List[CalendarEvent]:
        """Get central bank meetings and rate decisions."""
        events = await self.get_events(
            countries=["US", "CA", "EU", "GB", "JP", "CH"],
            date_from=date.today(),
            date_to=date.today() + timedelta(days=30),
            importance=["high"],
        )
        # Filter for central bank events
        cb_keywords = ["rate decision", "monetary policy", "fed", "boc", "ecb", "boe", "boj", "snb", "fomc", "interest rate"]
        return [e for e in events if any(kw in e.event_name.lower() for kw in cb_keywords)]