"""
Tests for data validators and formatters.
"""
import pytest
from datetime import datetime, date, timezone
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
    MorningBriefing,
    BriefingStatus,
    DataSource,
)


class TestMarketDataPoint:
    """Tests for MarketDataPoint model."""

    def test_market_data_point_creation(self):
        """Test basic market data point creation."""
        point = MarketDataPoint(
            value=Decimal("100.50"),
            currency="USD",
            unit="per barrel",
            timestamp=datetime.utcnow(),
            source=DataSource.ALPHA_VANTAGE,
        )
        assert point.value == Decimal("100.50")
        assert point.currency == "USD"
        assert point.unit == "per barrel"

    def test_market_data_point_with_changes(self):
        """Test market data point with change calculations."""
        point = MarketDataPoint(
            value=Decimal("100.00"),
            currency="USD",
            unit="points",
            timestamp=datetime.utcnow(),
            source=DataSource.ALPHA_VANTAGE,
            change_24h=Decimal("2.50"),
            change_24h_pct=Decimal("2.5"),
        )
        assert point.change_24h == Decimal("2.50")
        assert point.change_24h_pct == Decimal("2.5")


class TestOilPrice:
    """Tests for OilPrice model."""

    def test_oil_price_creation(self):
        """Test oil price creation."""
        oil = OilPrice(
            benchmark="BRENT",
            value=Decimal("85.50"),
            currency="USD",
            unit="per barrel",
            timestamp=datetime.utcnow(),
            source=DataSource.EIA,
        )
        assert oil.benchmark == "BRENT"
        assert oil.price_per_barrel == Decimal("85.50")


class TestCryptoPrice:
    """Tests for CryptoPrice model."""

    def test_crypto_price_creation(self):
        """Test crypto price creation."""
        crypto = CryptoPrice(
            symbol="BTC",
            value=Decimal("45000"),
            currency="USD",
            unit="per coin",
            timestamp=datetime.utcnow(),
            source=DataSource.COINGECKO,
            price_usd=Decimal("45000"),
            price_cad=Decimal("61000"),
        )
        assert crypto.symbol == "BTC"
        assert crypto.price_usd == Decimal("45000")
        assert crypto.price_cad == Decimal("61000")


class TestBondYield:
    """Tests for BondYield model."""

    def test_bond_yield_creation(self):
        """Test bond yield creation."""
        bond = BondYield(
            country="CA",
            maturity_years=5,
            value=Decimal("4.25"),
            currency="CAD",
            unit="percent",
            timestamp=datetime.utcnow(),
            source=DataSource.BANK_OF_CANADA,
        )
        assert bond.country == "CA"
        assert bond.maturity_years == 5
        assert bond.yield_pct == Decimal("4.25")


class TestWeatherData:
    """Tests for WeatherData model."""

    def test_weather_data_creation(self):
        """Test weather data creation."""
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
            weather_description="Partly cloudy",
        )
        assert weather.city == "Montreal"
        assert weather.current_temp_c == Decimal("15.5")
        assert weather.precipitation_probability_pct == 30


class TestNewsItem:
    """Tests for NewsItem model."""

    def test_news_item_creation(self):
        """Test news item creation."""
        news = NewsItem(
            headline="Bank of Canada holds rate at 5%",
            summary="The BoC maintained its policy rate...",
            source="Reuters",
            url="https://reuters.com/article/...",
            published_at=datetime.utcnow(),
            category="central_bank",
            regions=["CA"],
            language="en",
        )
        assert news.headline == "Bank of Canada holds rate at 5%"
        assert "CA" in news.regions
        assert news.category == "central_bank"


class TestCalendarEvent:
    """Tests for CalendarEvent model."""

    def test_calendar_event_creation(self):
        """Test calendar event creation."""
        event = CalendarEvent(
            event_name="BoC Interest Rate Decision",
            country="CA",
            date=date.today(),
            time="14:45",
            timezone="America/Toronto",
            importance="high",
            category="central_bank",
        )
        assert event.event_name == "BoC Interest Rate Decision"
        assert event.country == "CA"
        assert event.importance == "high"


class TestMorningBriefing:
    """Tests for MorningBriefing model."""

    def test_briefing_creation(self):
        """Test briefing creation."""
        briefing = MorningBriefing(
            id=uuid4(),
            briefing_date=date.today(),
            timezone="America/Toronto",
            language="en",
            mode="full",
            status=BriefingStatus.PENDING,
        )
        assert briefing.date == date.today()
        assert briefing.status == BriefingStatus.PENDING

    def test_markets_summary(self):
        """Test markets summary generation."""
        briefing = MorningBriefing(
            briefing_date=date.today(),
            markets={
                "oil": [
                    OilPrice(
                        benchmark="BRENT",
                        value=Decimal("85.00"),
                        currency="USD",
                        unit="per barrel",
                        timestamp=datetime.now(timezone.utc),
                        source=DataSource.EIA,
                    )
                ],
                "crypto": [
                    CryptoPrice(
                        symbol="BTC",
                        value=Decimal("45000"),
                        currency="USD",
                        unit="per coin",
                        timestamp=datetime.now(timezone.utc),
                        source=DataSource.COINGECKO,
                        price_usd=Decimal("45000"),
                    )
                ],
                "bonds": [
                    BondYield(
                        country="CA",
                        maturity_years=5,
                        value=Decimal("4.25"),
                        currency="CAD",
                        unit="percent",
                        timestamp=datetime.now(timezone.utc),
                        source=DataSource.BANK_OF_CANADA,
                    )
                ],
            },
        )
        summary = briefing.get_markets_summary()
        assert "BRENT" in summary
        assert "85.00" in summary
        assert "BTC" in summary
        assert "CA 5Y" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])