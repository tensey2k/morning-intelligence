"""
Tests for data sources and briefing engine.
"""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.data_sources.alpha_vantage import AlphaVantageSource
from src.data_sources.bank_of_canada import BankOfCanadaSource
from src.data_sources.coingecko import CoinGeckoSource
from src.data_sources.open_meteo import OpenMeteoSource
from src.data_sources.finance_calendar import FinanceCalendarSource
from src.data_sources.rss_news import RSSNewsSource
from src.data_sources.manager import DataSourceManager
from src.briefing.engine import BriefingEngine
from src.models import (
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


class TestAlphaVantageSource:
    """Tests for Alpha Vantage data source."""

    @pytest.fixture
    def source(self):
        return AlphaVantageSource()

    @pytest.mark.asyncio
    async def test_health_check(self, source):
        with patch.object(source, '_request', return_value={"Global Quote": {}}):
            result = await source.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_wti_price(self, source):
        mock_response = {
            "data": [{"date": "2024-01-15", "value": "75.50"}]
        }
        with patch.object(source, '_request', return_value=mock_response):
            result = await source.get_wti_price()
            assert result is not None
            assert result.benchmark == "WTI"
            assert result.price_per_barrel == 75.50

    @pytest.mark.asyncio
    async def test_get_brent_price(self, source):
        mock_response = {
            "data": [{"date": "2024-01-15", "value": "80.25"}]
        }
        with patch.object(source, '_request', return_value=mock_response):
            result = await source.get_brent_price()
            assert result is not None
            assert result.benchmark == "BRENT"
            assert result.price_per_barrel == 80.25


class TestBankOfCanadaSource:
    """Tests for Bank of Canada data source."""

    @pytest.fixture
    def source(self):
        return BankOfCanadaSource()

    @pytest.mark.asyncio
    async def test_health_check(self, source):
        with patch.object(source, '_fetch_series', return_value={"observations": [{"d": "2024-01-15", "FXUSDCAD": {"v": "1.35"}}]}):
            result = await source.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_bond_yields(self, source):
        # Mock different responses for each series ID
        mock_responses = {
            "BD.CDN.2YR.DQ.YLD": {"observations": [{"d": "2024-01-15", "BD.CDN.2YR.DQ.YLD": {"v": "4.25"}}]},
            "BD.CDN.3YR.DQ.YLD": {"observations": [{"d": "2024-01-15", "BD.CDN.3YR.DQ.YLD": {"v": "4.00"}}]},
            "BD.CDN.5YR.DQ.YLD": {"observations": [{"d": "2024-01-15", "BD.CDN.5YR.DQ.YLD": {"v": "3.75"}}]},
            "BD.CDN.7YR.DQ.YLD": {"observations": [{"d": "2024-01-15", "BD.CDN.7YR.DQ.YLD": {"v": "3.60"}}]},
            "BD.CDN.10YR.DQ.YLD": {"observations": [{"d": "2024-01-15", "BD.CDN.10YR.DQ.YLD": {"v": "3.50"}}]},
            "BD.CDN.LONG.DQ.YLD": {"observations": [{"d": "2024-01-15", "BD.CDN.LONG.DQ.YLD": {"v": "3.40"}}]},
            "BD.CDN.RRB.DQ.YLD": {"observations": [{"d": "2024-01-15", "BD.CDN.RRB.DQ.YLD": {"v": "1.50"}}]},
        }

        def mock_fetch_series(series_id):
            return mock_responses.get(series_id, {"observations": []})

        with patch.object(source, '_fetch_series', side_effect=mock_fetch_series):
            results = await source.get_bond_yields()
            assert len(results) >= 2
            assert all(isinstance(r, BondYield) for r in results)

    @pytest.mark.asyncio
    async def test_get_policy_rate(self, source):
        mock_response = {
            "observations": [{"d": "2024-01-15", "B114039": {"v": "5.00"}}]
        }
        with patch.object(source, '_fetch_series', return_value=mock_response):
            result = await source.get_policy_rate()
            assert result is not None
            assert result.maturity_years == 0
            assert result.yield_pct == 5.00


class TestCoinGeckoSource:
    """Tests for CoinGecko data source."""

    @pytest.fixture
    def source(self):
        return CoinGeckoSource()

    @pytest.mark.asyncio
    async def test_health_check(self, source):
        with patch.object(source, '_request', return_value={"gecko_says": "OK"}):
            result = await source.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_crypto_prices(self, source):
        mock_response = {
            "bitcoin": {"usd": 45000, "cad": 60000, "usd_24h_change": 2.5},
            "ethereum": {"usd": 2500, "cad": 3300, "usd_24h_change": -1.2},
        }
        with patch.object(source, '_request', return_value=mock_response):
            results = await source.get_crypto_prices()
            assert len(results) == 2
            btc = next(r for r in results if r.symbol == "BTC")
            assert btc.price_usd == 45000
            assert btc.price_cad == 60000


class TestOpenMeteoSource:
    """Tests for Open-Meteo weather source."""

    @pytest.fixture
    def source(self):
        return OpenMeteoSource()

    @pytest.mark.asyncio
    async def test_health_check(self, source):
        with patch.object(source, '_request', return_value={"current_weather": {"temperature": 0}}):
            result = await source.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_weather(self, source):
        mock_response = {
            "current_weather": {
                "temperature": -5,
                "windspeed": 15,
                "winddirection": 270,
                "weathercode": 3,
            },
            "daily": {
                "time": ["2024-01-15"],
                "temperature_2m_max": [2],
                "temperature_2m_min": [-8],
                "precipitation_probability_max": [30],
                "precipitation_sum": [0.5],
                "weather_code": [3],
            },
            "timezone": "America/Toronto",
        }
        with patch.object(source, '_request', return_value=mock_response):
            result = await source.get_weather(latitude=45.5, longitude=-73.5)
            assert result.city == "Montreal"
            assert result.current_temp_c == -5
            assert result.high_temp_c == 2
            assert result.low_temp_c == -8


class TestFinanceCalendarSource:
    """Tests for FinanceCalendar source."""

    @pytest.fixture
    def source(self):
        return FinanceCalendarSource()

    @pytest.mark.asyncio
    async def test_health_check(self, source):
        with patch.object(source, '_request', return_value={"data": []}):
            result = await source.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_events(self, source):
        mock_response = {
            "data": [
                {
                    "event": "Bank of Canada Rate Decision",
                    "country": "CA",
                    "date": "2024-01-24",
                    "time": "15:00",
                    "timezone": "America/Toronto",
                    "actual": "5.00%",
                    "forecast": "5.00%",
                    "previous": "5.00%",
                    "importance": "high",
                    "category": "central_bank",
                }
            ]
        }
        with patch.object(source, '_request', return_value=mock_response):
            results = await source.get_events(countries=["CA"])
            assert len(results) == 1
            assert results[0].event_name == "Bank of Canada Rate Decision"
            assert results[0].importance == "high"


class TestRSSNewsSource:
    """Tests for RSS News source."""

    @pytest.fixture
    def source(self):
        return RSSNewsSource()

    @pytest.mark.asyncio
    async def test_parse_entry(self, source):
        # Mock feedparser entry
        entry = MagicMock()
        entry.title = "Test Headline"
        entry.summary = "Test summary"
        entry.link = "https://example.com/article"
        entry.published_parsed = (2024, 1, 15, 10, 30, 0, 0, 0, 0)
        entry.get = MagicMock(side_effect=lambda k, d=None: getattr(entry, k, d))

        feed_info = {"category": "markets", "regions": ["CA"], "language": "en"}
        result = source._parse_entry(entry, feed_info)

        assert result is not None
        assert result.headline == "Test Headline"
        assert "CA" in result.regions


class TestDataSourceManager:
    """Tests for DataSourceManager."""

    @pytest.fixture
    def manager(self):
        return DataSourceManager()

    @pytest.mark.asyncio
    async def test_health_check_all(self, manager):
        with patch.object(manager.alpha_vantage, 'health_check', return_value=True), \
             patch.object(manager.bank_of_canada, 'health_check', return_value=True), \
             patch.object(manager.coingecko, 'health_check', return_value=True), \
             patch.object(manager.open_meteo, 'health_check', return_value=True), \
             patch.object(manager.finance_calendar, 'health_check', return_value=True), \
             patch.object(manager.rss_news, 'health_check', return_value=True), \
             patch.object(manager.fred, 'health_check', return_value=True), \
             patch.object(manager.eia, 'health_check', return_value=True), \
             patch.object(manager.marketaux, 'health_check', return_value=True):

            results = await manager.health_check_all()
            assert all(results.values())

    @pytest.mark.asyncio
    async def test_collect_briefing_data(self, manager):
        # Mock all data source methods
        with patch.object(manager, 'get_all_market_data', return_value={
            "oil": [], "crypto": [], "bonds": [], "policy_rates": [],
            "indices": [], "forex": [], "errors": []
        }), patch.object(manager, 'get_weather', return_value=None), \
             patch.object(manager, 'get_morocco_weather', return_value=None), \
             patch.object(manager, 'get_top_news', return_value=[]), \
             patch.object(manager, 'get_week_calendar', return_value=[]), \
             patch.object(manager, 'get_canadian_economic_data', return_value={}):

            data = await manager.collect_briefing_data()
            assert "market_data" in data
            assert "news" in data
            assert "calendar" in data


class TestBriefingEngine:
    """Tests for BriefingEngine."""

    @pytest.fixture
    def engine(self):
        return BriefingEngine()

    @pytest.mark.asyncio
    async def test_generate_briefing_structure(self, engine):
        # Mock data collection
        mock_data = {
            "market_data": {"oil": [], "crypto": [], "bonds": [], "policy_rates": [],
                          "indices": [], "forex": [], "errors": []},
            "weather": None,
            "morocco_weather": None,
            "news": [],
            "calendar": [],
            "canadian_economic": {},
            "collection_errors": [],
        }

        with patch.object(engine.data_sources, 'collect_briefing_data', return_value=mock_data), \
             patch.object(engine.llm, 'structure_briefing', return_value={
                 "executive_summary": "Test summary",
                 "markets_dashboard": "Test markets",
                 "major_global_news": "Test news",
                 "three_priorities": ["Priority 1", "Priority 2", "Priority 3"],
             }):

            briefing = await engine.generate_briefing()

            assert briefing is not None
            assert briefing.executive_summary == "Test summary"
            assert len(briefing.priorities) == 3


class TestModels:
    """Tests for Pydantic models."""

    def test_oil_price_model(self):
        oil = OilPrice(
            benchmark="WTI",
            value=75.50,
            currency="USD",
            unit="per barrel",
            timestamp=datetime.utcnow(),
            source=DataSource.ALPHA_VANTAGE,
        )
        assert oil.benchmark == "WTI"
        assert oil.price_per_barrel == 75.50

    def test_crypto_price_model(self):
        crypto = CryptoPrice(
            symbol="BTC",
            value=45000,
            currency="USD",
            unit="per coin",
            timestamp=datetime.utcnow(),
            source=DataSource.COINGECKO,
            price_usd=45000,
            price_cad=60000,
        )
        assert crypto.symbol == "BTC"
        assert crypto.price_usd == 45000
        assert crypto.price_cad == 60000

    def test_bond_yield_model(self):
        bond = BondYield(
            country="CA",
            maturity_years=5,
            value=3.75,
            currency="CAD",
            unit="percent",
            timestamp=datetime.utcnow(),
            source=DataSource.BANK_OF_CANADA,
        )
        assert bond.country == "CA"
        assert bond.maturity_years == 5
        assert bond.yield_pct == 3.75

    def test_weather_data_model(self):
        weather = WeatherData(
            city="Montreal",
            country="Canada",
            latitude=45.5,
            longitude=-73.5,
            current_temp_c=-5,
            high_temp_c=2,
            low_temp_c=-8,
            precipitation_probability_pct=30,
            weather_description="Overcast",
        )
        assert weather.city == "Montreal"
        assert weather.current_temp_c == -5

    def test_news_item_model(self):
        news = NewsItem(
            headline="Test Headline",
            summary="Test summary",
            source="Reuters",
            url="https://reuters.com/article",
            published_at=datetime.utcnow(),
            category="markets",
            regions=["CA", "US"],
        )
        assert news.headline == "Test Headline"
        assert "CA" in news.regions

    def test_calendar_event_model(self):
        event = CalendarEvent(
            event_name="BoC Rate Decision",
            country="CA",
            date=date.today(),
            time="15:00",
            importance="high",
            category="central_bank",
        )
        assert event.event_name == "BoC Rate Decision"
        assert event.importance == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])