"""
Tests for Telegram formatters.
"""
import pytest
from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4

from src.models import (
    MarketDataPoint,
    OilPrice,
    CryptoPrice,
    BondYield,
    StockIndex,
    ForexRate,
    WeatherData,
    NewsItem,
    CalendarEvent,
    DataSource,
)
from src.telegram.formatters import (
    format_markets,
    format_weather,
    format_news,
    format_status,
    format_help,
    format_settings,
    format_calendar,
)


class TestFormatMarkets:
    """Tests for format_markets function."""

    def test_format_markets_with_all_data(self):
        """Test formatting markets with all data types."""
        market_data = {
            "oil": [
                OilPrice(
                    benchmark="BRENT",
                    value=Decimal("85.50"),
                    currency="USD",
                    unit="per barrel",
                    timestamp=datetime.utcnow(),
                    source=DataSource.EIA,
                ),
                OilPrice(
                    benchmark="WTI",
                    value=Decimal("82.30"),
                    currency="USD",
                    unit="per barrel",
                    timestamp=datetime.utcnow(),
                    source=DataSource.EIA,
                ),
            ],
            "crypto": [
                CryptoPrice(
                    symbol="BTC",
                    value=Decimal("45000"),
                    currency="USD",
                    unit="per coin",
                    timestamp=datetime.utcnow(),
                    source=DataSource.COINGECKO,
                    price_usd=Decimal("45000"),
                    price_cad=Decimal("61000"),
                ),
            ],
            "bonds": [
                BondYield(
                    country="CA",
                    maturity_years=5,
                    value=Decimal("4.25"),
                    currency="CAD",
                    unit="percent",
                    timestamp=datetime.utcnow(),
                    source=DataSource.BANK_OF_CANADA,
                ),
            ],
            "indices": [
                StockIndex(
                    index_name="S&P 500",
                    value=Decimal("4500"),
                    currency="USD",
                    unit="points",
                    timestamp=datetime.utcnow(),
                    source=DataSource.ALPHA_VANTAGE,
                ),
            ],
            "forex": [
                ForexRate(
                    base_currency="USD",
                    quote_currency="CAD",
                    value=Decimal("1.35"),
                    currency="CAD",
                    unit="USD/CAD",
                    timestamp=datetime.utcnow(),
                    source=DataSource.ALPHA_VANTAGE,
                ),
            ],
            "errors": [],
        }

        result = format_markets(market_data)

        assert "MARKETS DASHBOARD" in result
        assert "OIL" in result
        assert "BRENT" in result
        assert "85.50" in result
        assert "WTI" in result
        assert "CRYPTOCURRENCY" in result
        assert "BTC" in result
        assert "45,000" in result  # Formatter outputs with comma
        assert "BOND YIELDS" in result
        assert "CA" in result
        assert "4.25" in result
        assert "STOCK INDICES" in result
        assert "S&P 500" in result
        assert "FOREX" in result
        assert "USD/CAD" in result


class TestFormatWeather:
    """Tests for format_weather function."""

    def test_format_weather_complete(self):
        """Test formatting complete weather data."""
        weather = WeatherData(
            city="Montreal",
            country="Canada",
            latitude=45.5017,
            longitude=-73.5673,
            current_temp_c=Decimal("15.5"),
            feels_like_c=Decimal("14.0"),
            high_temp_c=Decimal("18.0"),
            low_temp_c=Decimal("10.0"),
            precipitation_probability_pct=30,
            wind_speed_kmh=Decimal("15.0"),
            wind_direction="SW",
            weather_description="Partly cloudy",
            alerts=["Wind advisory in effect"],
            forecast_daily=[
                {
                    "date": "2024-01-15",
                    "high_temp_c": 18.0,
                    "low_temp_c": 10.0,
                    "precip_probability_pct": 30,
                    "weather_description": "Partly cloudy",
                }
            ],
        )

        result = format_weather(weather)

        assert "WEATHER - Montreal, Canada" in result
        assert "15.5°C" in result
        assert "14.0°C" in result
        assert "18.0°C / 10.0°C" in result
        assert "30%" in result
        assert "15 km/h" in result  # Formatter outputs without .0
        assert "SW" in result
        assert "Partly cloudy" in result
        assert "Wind advisory" in result
        assert "3-DAY FORECAST" in result


class TestFormatNews:
    """Tests for format_news function."""

    def test_format_news_multiple_items(self):
        """Test formatting multiple news items."""
        news_items = [
            NewsItem(
                headline="BoC holds rate at 5%",
                summary="The Bank of Canada maintained its policy rate...",
                source="Reuters",
                url="https://reuters.com/article/1",
                published_at=datetime(2024, 1, 15, 14, 30),
                category="central_bank",
                regions=["CA"],
            ),
            NewsItem(
                headline="Oil prices rise on supply concerns",
                summary="Brent crude rose above $85...",
                source="Bloomberg",
                url="https://bloomberg.com/article/2",
                published_at=datetime(2024, 1, 15, 12, 0),
                category="energy",
                regions=["global"],
            ),
        ]

        result = format_news(news_items, "all")

        assert "TOP NEWS" in result
        assert "BoC holds rate at 5%" in result
        assert "Bank of Canada maintained" in result
        assert "🇨🇦" in result  # Canada region emoji
        assert "Oil prices rise" in result
        # Note: formatter doesn't add emoji for "global" region, only for specific countries
        assert "Read more" in result


class TestFormatStatus:
    """Tests for format_status function."""

    def test_format_status_all_healthy(self):
        """Test formatting status with all healthy sources."""
        health = {
            "Alpha Vantage": True,
            "Bank of Canada Valet": True,
            "CoinGecko": True,
            "Open-Meteo": True,
            "FinanceCalendar": True,
            "RSS News Aggregator": True,
            "FRED": True,
            "EIA": True,
            "MarketAux": True,
        }
        next_run = datetime(2024, 1, 16, 9, 0)
        last_briefing = None
        scheduler_status = {
            "running": True,
            "timezone": "America/Toronto",
            "jobs_count": 1,
            "next_run": next_run.isoformat(),
            "uptime": "Running",
        }

        result = format_status(health, next_run, last_briefing, scheduler_status)

        assert "SYSTEM STATUS" in result
        assert "DATA SOURCES" in result
        assert "✅ Alpha Vantage" in result
        assert "✅ Bank of Canada Valet" in result
        assert "SCHEDULER" in result
        assert "Running: ✅" in result
        assert "America/Toronto" in result


class TestFormatHelp:
    """Tests for format_help function."""

    def test_format_help_contains_commands(self):
        """Test help message contains all commands."""
        result = format_help()

        assert "MORNING INTELLIGENCE - HELP" in result
        assert "/start" in result
        assert "/help" in result
        assert "/briefing" in result
        assert "/markets" in result
        assert "/news" in result
        assert "/weather" in result
        assert "/calendar" in result
        assert "/mortgage" in result
        assert "/savings" in result
        assert "/settings" in result
        assert "/status" in result


class TestFormatSettings:
    """Tests for format_settings function."""

    def test_format_settings_with_user_settings(self):
        """Test formatting settings with user settings object."""
        class MockSettings:
            briefing_hour = 9
            briefing_minute = 0
            timezone = "America/Toronto"
            schedule_weekdays_only = False
            weather_city = "Montreal"
            weather_country = "Canada"
            default_language = "en"
            briefing_mode = "full"

        settings = MockSettings()
        result = format_settings(settings)

        assert "CURRENT SETTINGS" in result
        assert "09:00" in result
        assert "America/Toronto" in result
        assert "Daily" in result
        assert "Montreal" in result
        assert "en" in result
        assert "full" in result


class TestFormatCalendar:
    """Tests for format_calendar function."""

    def test_format_calendar_with_events(self):
        """Test formatting calendar with events."""
        events = [
            CalendarEvent(
                event_name="BoC Interest Rate Decision",
                country="CA",
                date=date(2024, 1, 24),
                time="14:45",
                timezone="America/Toronto",
                importance="high",
                category="central_bank",
            ),
            CalendarEvent(
                event_name="US CPI Release",
                country="US",
                date=date(2024, 1, 25),
                time="08:30",
                timezone="America/New_York",
                importance="high",
                category="inflation",
                forecast="3.1%",
                previous="3.2%",
            ),
        ]

        result = format_calendar(events, "week")

        assert "ECONOMIC CALENDAR" in result
        assert "BoC Interest Rate Decision" in result
        assert "🔴" in result  # High importance
        assert "CA" in result
        assert "US CPI Release" in result
        assert "Forecast: 3.1%" in result
        assert "Previous: 3.2%" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])