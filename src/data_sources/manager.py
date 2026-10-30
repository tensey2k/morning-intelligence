"""
Data Source Manager - coordinates all data sources for the briefing engine.
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.alpha_vantage import AlphaVantageSource
from src.data_sources.bank_of_canada import BankOfCanadaSource
from src.data_sources.coingecko import CoinGeckoSource
from src.data_sources.open_meteo import OpenMeteoSource
from src.data_sources.finance_calendar import FinanceCalendarSource
from src.data_sources.rss_news import RSSNewsSource
from src.data_sources.fred import FredSource
from src.data_sources.eia import EIASource
from src.data_sources.marketaux import MarketAuxSource
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import (
    BondYield,
    CalendarEvent,
    CryptoPrice,
    ForexRate,
    MarketDataPoint,
    NewsItem,
    OilPrice,
    StockIndex,
    WeatherData,
)


class DataSourceManager:
    """Manages all data sources and provides unified access for briefing generation."""

    def __init__(self):
        self.alpha_vantage = AlphaVantageSource()
        self.bank_of_canada = BankOfCanadaSource()
        self.coingecko = CoinGeckoSource()
        self.open_meteo = OpenMeteoSource()
        self.finance_calendar = FinanceCalendarSource()
        self.rss_news = RSSNewsSource()
        self.fred = FredSource()
        self.eia = EIASource()
        self.marketaux = MarketAuxSource()

        self._sources: List[DataSourceBase] = [
            self.alpha_vantage,
            self.bank_of_canada,
            self.coingecko,
            self.open_meteo,
            self.finance_calendar,
            self.rss_news,
            self.fred,
            self.eia,
            self.marketaux,
        ]

    async def close_all(self):
        """Close all HTTP clients."""
        for source in self._sources:
            await source.close()

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all data sources."""
        results = {}
        for source in self._sources:
            try:
                results[source.name] = await source.health_check()
            except Exception:
                results[source.name] = False
        return results

    # =========================================================================
    # MARKET DATA
    # =========================================================================
    async def get_oil_prices(self) -> List[OilPrice]:
        """Get Brent and WTI oil prices."""
        results = []

        # Try EIA first (most reliable for oil)
        try:
            eia_prices = await self.eia.get_all_crude_prices()
            results.extend(eia_prices)
        except Exception:
            pass

        # Fallback to Alpha Vantage
        if not results:
            try:
                wti = await self.alpha_vantage.get_wti_price()
                brent = await self.alpha_vantage.get_brent_price()
                if wti:
                    results.append(wti)
                if brent:
                    results.append(brent)
            except Exception:
                pass

        # Fallback to FRED
        if not results:
            try:
                fred_oil = await self.fred.get_oil_prices()
                for oil in fred_oil:
                    results.append(OilPrice(
                        benchmark=oil.metadata.get("benchmark", "UNKNOWN").replace(" Crude Oil", "").replace(" ", "_"),
                        value=oil.value,
                        currency=oil.currency,
                        unit=oil.unit,
                        timestamp=oil.timestamp,
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata=oil.metadata,
                    ))
            except Exception:
                pass

        return results

    async def get_crypto_prices(self) -> List[CryptoPrice]:
        """Get crypto prices (BTC, ETH in USD and CAD)."""
        # Try CoinGecko first (better for CAD prices)
        try:
            return await self.coingecko.get_crypto_prices()
        except Exception:
            pass

        # Fallback to Alpha Vantage
        try:
            return await self.alpha_vantage.get_crypto_prices()
        except Exception as e:
            raise DataSourceError(f"All crypto price sources failed: {e}", "DataSourceManager")

    async def get_bond_yields(self) -> List[BondYield]:
        """Get all bond yields (CA and US)."""
        results = []

        # Canadian bonds from Bank of Canada
        try:
            ca_yields = await self.bank_of_canada.get_bond_yields()
            results.extend(ca_yields)
        except Exception:
            pass

        # US bonds from FRED (more reliable than Alpha Vantage)
        try:
            us_yields = await self.fred.get_treasury_yields()
            results.extend(us_yields)
        except Exception:
            pass

        # Fallback to Alpha Vantage for US
        if not any(b.country == "US" for b in results):
            try:
                us_yields = await self.alpha_vantage.get_treasury_yields()
                results.extend(us_yields)
            except Exception:
                pass

        if not results:
            raise DataSourceError("All bond yield sources failed", "DataSourceManager")

        return results

    async def get_policy_rates(self) -> List[BondYield]:
        """Get central bank policy rates."""
        results = []

        # Bank of Canada policy rate
        try:
            boc_rate = await self.bank_of_canada.get_policy_rate()
            if boc_rate:
                results.append(boc_rate)
        except Exception:
            pass

        # Fed funds rate from FRED
        try:
            fed_rate = await self.fred.get_fed_funds_rate()
            if fed_rate:
                results.append(fed_rate)
            fed_target = await self.fred.get_fed_target_rate()
            if fed_target:
                results.append(fed_target)
        except Exception:
            pass

        # Fallback to Alpha Vantage
        if not any(b.metadata.get("type") == "federal_funds_rate" for b in results):
            try:
                av_yields = await self.alpha_vantage.get_treasury_yields()
                for y in av_yields:
                    if y.metadata.get("type") == "federal_funds_rate":
                        results.append(y)
                        break
            except Exception:
                pass

        return results

    async def get_yield_spreads(self) -> List[MarketDataPoint]:
        """Get key yield curve spreads."""
        try:
            return await self.fred.get_yield_spreads()
        except Exception:
            return []

    async def get_stock_indices(self) -> List[StockIndex]:
        """Get major stock indices."""
        try:
            return await self.alpha_vantage.get_stock_indices()
        except Exception as e:
            raise DataSourceError(f"Stock indices failed: {e}", "DataSourceManager")

    async def get_forex_rates(self) -> List[ForexRate]:
        """Get forex rates."""
        results = []

        # Alpha Vantage for major pairs
        try:
            av_rates = await self.alpha_vantage.get_forex_rates()
            results.extend(av_rates)
        except Exception:
            pass

        # Bank of Canada for CAD crosses (official source)
        try:
            boc_rates = await self.bank_of_canada.get_exchange_rates()
            for rate in boc_rates:
                base = rate.metadata.get("base_currency", "")
                if base:
                    results.append(ForexRate(
                        base_currency=base,
                        quote_currency="CAD",
                        value=rate.value,
                        currency="CAD",
                        unit=f"{base}/CAD",
                        timestamp=rate.timestamp,
                        source=rate.source,
                        is_delayed=rate.is_delayed,
                    ))
        except Exception:
            pass

        # FRED for Dollar Index
        try:
            dollar_idx = await self.fred.get_dollar_index()
            if dollar_idx:
                # Add as a special forex entry
                pass
        except Exception:
            pass

        return results

    async def get_all_market_data(self) -> Dict[str, Any]:
        """Get all market data in parallel."""
        import asyncio

        results = await asyncio.gather(
            self.get_oil_prices(),
            self.get_crypto_prices(),
            self.get_bond_yields(),
            self.get_policy_rates(),
            self.get_yield_spreads(),
            self.get_stock_indices(),
            self.get_forex_rates(),
            return_exceptions=True,
        )

        return {
            "oil": results[0] if not isinstance(results[0], Exception) else [],
            "crypto": results[1] if not isinstance(results[1], Exception) else [],
            "bonds": results[2] if not isinstance(results[2], Exception) else [],
            "policy_rates": results[3] if not isinstance(results[3], Exception) else [],
            "yield_spreads": results[4] if not isinstance(results[4], Exception) else [],
            "indices": results[5] if not isinstance(results[5], Exception) else [],
            "forex": results[6] if not isinstance(results[6], Exception) else [],
            "errors": [str(r) for r in results if isinstance(r, Exception)],
        }

    # =========================================================================
    # WEATHER
    # =========================================================================
    async def get_weather(self) -> WeatherData:
        """Get primary location weather (Montreal)."""
        return await self.open_meteo.get_montreal_weather()

    async def get_morocco_weather(self) -> WeatherData:
        """Get Morocco weather (Casablanca)."""
        return await self.open_meteo.get_morocco_weather()

    # =========================================================================
    # NEWS
    # =========================================================================
    async def get_top_news(self, max_items: int = 30) -> List[NewsItem]:
        """Get curated top news for briefing (combines RSS + MarketAux)."""
        import asyncio

        # Fetch from both sources
        rss_news, marketaux_news = await asyncio.gather(
            self.rss_news.get_top_news(max_total=max_total),
            self.marketaux.get_curated_briefing_news(max_total=max_total),
            return_exceptions=True,
        )

        all_items = []
        if isinstance(rss_news, list):
            all_items.extend(rss_news)
        if isinstance(marketaux_news, list):
            all_items.extend(marketaux_news)

        # Deduplicate by headline similarity
        seen_headlines = set()
        unique_items = []
        for item in all_items:
            headline_key = item.headline.lower().strip()[:50]
            if headline_key not in seen_headlines:
                seen_headlines.add(headline_key)
                unique_items.append(item)

        # Sort by relevance
        def relevance_score(item: NewsItem) -> float:
            score = 0.0
            hours_old = (datetime.now(timezone.utc) - item.published_at).total_seconds() / 3600
            score += max(0, 1 - hours_old / 48)
            if item.category in ["central_bank", "markets", "energy", "monetary_policy", "interest_rates"]:
                score += 0.5
            elif item.category in ["business", "economy", "inflation", "gdp", "employment", "real_estate", "mortgage"]:
                score += 0.3
            if "CA" in item.regions:
                score += 0.3
            if "MA" in item.regions:
                score += 0.2
            return score

        unique_items.sort(key=relevance_score, reverse=True)
        return unique_items[:max_total]

    async def get_canadian_news(self, max_items: int = 15) -> List[NewsItem]:
        """Get Canadian financial news."""
        import asyncio
        rss, mx = await asyncio.gather(
            self.rss_news.get_canadian_news(max_items=max_items),
            self.marketaux.get_canadian_news(limit=max_items),
            return_exceptions=True,
        )
        items = []
        if isinstance(rss, list):
            items.extend(rss)
        if isinstance(mx, list):
            items.extend(mx)
        return items[:max_items]

    async def get_morocco_news(self, max_items: int = 8) -> List[NewsItem]:
        """Get Moroccan financial news."""
        import asyncio
        rss, mx = await asyncio.gather(
            self.rss_news.get_morocco_news(max_items=max_items),
            self.marketaux.get_morocco_news(limit=max_items),
            return_exceptions=True,
        )
        items = []
        if isinstance(rss, list):
            items.extend(rss)
        if isinstance(mx, list):
            items.extend(mx)
        return items[:max_items]

    async def get_energy_news(self, max_items: int = 8) -> List[NewsItem]:
        """Get energy/oil news."""
        import asyncio
        rss, mx = await asyncio.gather(
            self.rss_news.get_energy_news(max_items=max_items),
            self.marketaux.get_energy_news(limit=max_items),
            return_exceptions=True,
        )
        items = []
        if isinstance(rss, list):
            items.extend(rss)
        if isinstance(mx, list):
            items.extend(mx)
        return items[:max_items]

    async def get_central_bank_news(self, max_items: int = 10) -> List[NewsItem]:
        """Get central bank news."""
        import asyncio
        rss, mx = await asyncio.gather(
            self.rss_news.get_central_bank_news(max_items=max_items),
            self.marketaux.get_central_bank_news(limit=max_items),
            return_exceptions=True,
        )
        items = []
        if isinstance(rss, list):
            items.extend(rss)
        if isinstance(mx, list):
            items.extend(mx)
        return items[:max_items]

    async def get_housing_mortgage_news(self, max_items: int = 8) -> List[NewsItem]:
        """Get housing and mortgage news."""
        try:
            return await self.marketaux.get_housing_mortgage_news(limit=max_items)
        except Exception:
            return []

    async def get_economic_indicators_news(self, max_items: int = 8) -> List[NewsItem]:
        """Get economic indicators news."""
        try:
            return await self.marketaux.get_economic_indicators_news(limit=max_items)
        except Exception:
            return []

    # =========================================================================
    # ECONOMIC CALENDAR
    # =========================================================================
    async def get_today_calendar(self) -> List[CalendarEvent]:
        """Get today's economic calendar events."""
        return await self.finance_calendar.get_today_events()

    async def get_week_calendar(self) -> List[CalendarEvent]:
        """Get this week's economic calendar events."""
        return await self.finance_calendar.get_week_events()

    async def get_central_bank_events(self) -> List[CalendarEvent]:
        """Get central bank meetings."""
        return await self.finance_calendar.get_central_bank_events()

    # =========================================================================
    # US ECONOMIC DATA (from FRED)
    # =========================================================================
    async def get_us_economic_data(self) -> Dict[str, Any]:
        """Get all US economic data from FRED."""
        return await self.fred.get_all_us_economic_data()

    # =========================================================================
    # CANADIAN SPECIFIC DATA
    # =========================================================================
    async def get_canadian_economic_data(self) -> Dict[str, Any]:
        """Get all Canadian economic data from Bank of Canada."""
        return await self.bank_of_canada.get_all_canadian_data()

    # =========================================================================
    # OIL MARKET DATA (from EIA)
    # =========================================================================
    async def get_oil_market_data(self) -> Dict[str, Any]:
        """Get comprehensive oil market data from EIA."""
        return await self.eia.get_all_oil_market_data()

    # =========================================================================
    # COMPREHENSIVE BRIEFING DATA
    # =========================================================================
    async def collect_briefing_data(self) -> Dict[str, Any]:
        """Collect all data needed for morning briefing."""
        import asyncio
        from datetime import datetime

        # Run all data collection in parallel
        results = await asyncio.gather(
            self.get_all_market_data(),
            self.get_weather(),
            self.get_morocco_weather(),
            self.get_top_news(30),
            self.get_week_calendar(),
            self.get_canadian_economic_data(),
            self.get_us_economic_data(),
            self.get_oil_market_data(),
            return_exceptions=True,
        )

        market_data, weather, morocco_weather, news, calendar, ca_economic, us_economic, oil_market = results

        return {
            "market_data": market_data if not isinstance(market_data, Exception) else {"errors": [str(market_data)]},
            "weather": weather if not isinstance(weather, Exception) else None,
            "morocco_weather": morocco_weather if not isinstance(morocco_weather, Exception) else None,
            "news": news if not isinstance(news, Exception) else [],
            "calendar": calendar if not isinstance(calendar, Exception) else [],
            "canadian_economic": ca_economic if not isinstance(ca_economic, Exception) else {},
            "us_economic": us_economic if not isinstance(us_economic, Exception) else {},
            "oil_market": oil_market if not isinstance(oil_market, Exception) else {},
            "collection_errors": [str(r) for r in results if isinstance(r, Exception)],
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }


# Global instance
data_source_manager = DataSourceManager()