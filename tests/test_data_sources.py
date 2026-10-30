"""
Tests for data sources (mocked).
"""
import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.data_sources.base import DataSourceBase, DataSourceError, RateLimitError
from src.data_sources.alpha_vantage import AlphaVantageSource
from src.data_sources.bank_of_canada import BankOfCanadaSource
from src.data_sources.coingecko import CoinGeckoSource
from src.data_sources.open_meteo import OpenMeteoSource
from src.data_sources.fred import FredSource
from src.data_sources.eia import EIASource
from src.data_sources.marketaux import MarketAuxSource
from src.data_sources.rss_news import RSSNewsSource
from src.data_sources.finance_calendar import FinanceCalendarSource
from src.models import DataSource


class TestDataSourceBase:
    """Tests for base data source class."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test rate limit error handling."""
        # Create a concrete implementation for testing
        class TestDataSource(DataSourceBase):
            async def health_check(self) -> bool:
                return True

        source = TestDataSource("Test", "https://api.test.com")
        error = RateLimitError("Test", retry_after=60)
        assert error.source == "Test"
        assert error.details.get("retry_after") == 60


class TestAlphaVantageSource:
    """Tests for Alpha Vantage source (mocked)."""

    @pytest.fixture
    def source(self):
        return AlphaVantageSource()

    @pytest.mark.asyncio
    async def test_get_wti_price(self, source):
        """Test WTI price fetching."""
        with patch.object(source, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": [
                    {"date": "2024-01-15", "value": "82.50"}
                ]
            }
            result = await source.get_wti_price()
            assert result is not None
            assert result.benchmark == "WTI"
            assert result.value == Decimal("82.50")

    @pytest.mark.asyncio
    async def test_get_brent_price(self, source):
        """Test Brent price fetching."""
        with patch.object(source, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": [
                    {"date": "2024-01-15", "value": "85.00"}
                ]
            }
            result = await source.get_brent_price()
            assert result is not None
            assert result.benchmark == "BRENT"
            assert result.value == Decimal("85.00")

    @pytest.mark.asyncio
    async def test_get_stock_indices(self, source):
        """Test stock indices fetching."""
        with patch.object(source, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": [
                    {"date": "2024-01-15", "value": "4500.00"}
                ]
            }
            result = await source.get_stock_indices()
            assert isinstance(result, list)


class TestBankOfCanadaSource:
    """Tests for Bank of Canada source (mocked)."""

    @pytest.fixture
    def source(self):
        return BankOfCanadaSource()

    @pytest.mark.asyncio
    async def test_get_bond_yields(self, source):
        """Test bond yields fetching."""
        with patch.object(source, '_fetch_series', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "observations": [
                    {"d": "2024-01-15", "BD.CDN.5YR.DQ.YLD": {"v": "4.25"}}
                ]
            }
            result = await source.get_bond_yields()
            assert isinstance(result, list)
            if result:
                assert result[0].country == "CA"
                assert result[0].maturity_years == 5


class TestCoinGeckoSource:
    """Tests for CoinGecko source (mocked)."""

    @pytest.fixture
    def source(self):
        return CoinGeckoSource()

    @pytest.mark.asyncio
    async def test_get_crypto_prices(self, source):
        """Test crypto prices fetching."""
        with patch.object(source, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "bitcoin": {
                    "usd": 45000,
                    "cad": 61000,
                    "usd_24h_change": 2.5
                },
                "ethereum": {
                    "usd": 2500,
                    "cad": 3400,
                    "usd_24h_change": 1.8
                }
            }
            result = await source.get_crypto_prices()
            assert len(result) == 2
            btc = next((c for c in result if c.symbol == "BTC"), None)
            assert btc is not None
            assert btc.price_usd == Decimal("45000")
            assert btc.price_cad == Decimal("61000")
            assert btc.change_24h_pct == Decimal("2.5")


class TestOpenMeteoSource:
    """Tests for Open-Meteo source (mocked)."""

    @pytest.fixture
    def source(self):
        return OpenMeteoSource()

    @pytest.mark.asyncio
    async def test_get_weather(self, source):
        """Test weather fetching."""
        with patch.object(source, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "current_weather": {
                    "temperature": 15.5,
                    "windspeed": 15.0,
                    "winddirection": 225,
                    "weathercode": 2
                },
                "daily": {
                    "time": ["2024-01-15", "2024-01-16", "2024-01-17"],
                    "temperature_2m_max": [18.0, 16.0, 14.0],
                    "temperature_2m_min": [10.0, 8.0, 6.0],
                    "precipitation_probability_max": [30, 20, 10],
                    "precipitation_sum": [0.0, 0.0, 0.0],
                    "snowfall_sum": [0.0, 0.0, 0.0],
                    "wind_speed_10m_max": [15.0, 12.0, 10.0],
                    "weather_code": [2, 1, 0]
                }
            }
            result = await source.get_weather(latitude=45.5, longitude=-73.5)
            assert result.city == "Montreal"
            assert result.current_temp_c == Decimal("15.5")
            assert result.high_temp_c == Decimal("18.0")
            assert result.weather_description == "Partly cloudy"


class TestFredSource:
    """Tests for FRED source (mocked)."""

    @pytest.fixture
    def source(self):
        return FredSource()

    @pytest.mark.asyncio
    async def test_get_treasury_yields(self, source):
        """Test treasury yields fetching."""
        with patch.object(source, '_fetch_series', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [
                {"observations": [{"date": "2024-01-15", "value": "4.25"}]},
                {"observations": [{"date": "2024-01-15", "value": "4.15"}]},
                {"observations": [{"date": "2024-01-15", "value": "4.30"}]},
                {"observations": [{"date": "2024-01-15", "value": "4.40"}]},
            ]
            result = await source.get_treasury_yields()
            assert len(result) == 4
            maturities = [b.maturity_years for b in result]
            assert 2 in maturities
            assert 5 in maturities
            assert 10 in maturities
            assert 30 in maturities


class TestEIASource:
    """Tests for EIA source (mocked)."""

    @pytest.fixture
    def source(self):
        return EIASource()

    @pytest.mark.asyncio
    async def test_get_wti_price(self, source):
        """Test WTI price fetching from EIA."""
        with patch.object(source, '_fetch_series', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "response": {
                    "data": [
                        {"period": "2024-01-15", "value": 82.50}
                    ]
                }
            }
            result = await source.get_wti_price()
            assert result is not None
            assert result.benchmark == "WTI"
            assert result.value == Decimal("82.50")


class TestMarketAuxSource:
    """Tests for MarketAux source (mocked)."""

    @pytest.fixture
    def source(self):
        return MarketAuxSource()

    @pytest.mark.asyncio
    async def test_get_canadian_news(self, source):
        """Test Canadian news fetching."""
        with patch.object(source, '_fetch_news', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                MagicMock(
                    headline="BoC holds rate",
                    summary="Bank of Canada...",
                    source="MarketAux",
                    url="https://example.com/1",
                    published_at=datetime.utcnow(),
                    category="central_bank",
                    regions=["CA"],
                    language="en",
                )
            ]
            result = await source.get_canadian_news()
            assert len(result) == 1
            assert "BoC" in result[0].headline


class TestRSSNewsSource:
    """Tests for RSS News source (mocked)."""

    @pytest.fixture
    def source(self):
        return RSSNewsSource()

    @pytest.mark.asyncio
    async def test_fetch_feed(self, source):
        """Test RSS feed fetching."""
        with patch.object(source.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.text = """<?xml version="1.0"?>
            <rss><channel>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Test description</description>
                    <pubDate>Mon, 15 Jan 2024 14:30:00 GMT</pubDate>
                </item>
            </channel></rss>"""
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = await source._fetch_feed("https://example.com/feed")
            assert result is not None
            assert len(result.entries) == 1


class TestFinanceCalendarSource:
    """Tests for FinanceCalendar source (mocked)."""

    @pytest.fixture
    def source(self):
        return FinanceCalendarSource()

    @pytest.mark.asyncio
    async def test_get_events(self, source):
        """Test calendar events fetching."""
        with patch.object(source, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": [
                    {
                        "event": "BoC Rate Decision",
                        "country": "CA",
                        "date": "2024-01-24",
                        "time": "14:45",
                        "timezone": "America/Toronto",
                        "importance": "high",
                        "category": "central_bank",
                    }
                ]
            }
            result = await source.get_events()
            assert len(result) == 1
            assert result[0].event_name == "BoC Rate Decision"
            assert result[0].country == "CA"
            assert result[0].importance == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])