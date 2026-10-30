"""
Alpha Vantage data source for market data.
Provides: Oil (WTI/Brent), Bond yields, Stock indices, Forex, Crypto.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import (
    BondYield,
    CryptoPrice,
    DataSource,
    ForexRate,
    MarketDataPoint,
    OilPrice,
    StockIndex,
)


class AlphaVantageSource(DataSourceBase):
    """Alpha Vantage API client."""

    def __init__(self):
        super().__init__(
            name="Alpha Vantage",
            base_url=settings.alpha_vantage_base_url,
            api_key=settings.alpha_vantage_api_key,
            timeout=30.0,
            max_retries=3,
        )

    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "MorningIntelligence/1.0",
            "Accept": "application/json",
        }

    async def _request(self, params: Dict[str, str]) -> Any:
        """Make request to Alpha Vantage with API key."""
        params["apikey"] = self.api_key
        return await super()._request("GET", "", params=params)

    async def health_check(self) -> bool:
        """Check API availability with a simple quote request."""
        try:
            await self._request({"function": "GLOBAL_QUOTE", "symbol": "IBM"})
            return True
        except Exception:
            return False

    # =========================================================================
    # COMMODITIES - OIL
    # =========================================================================
    async def get_oil_prices(self) -> List[OilPrice]:
        """Get Brent and WTI crude oil prices."""
        results = []

        # WTI Crude Oil
        try:
            data = await self._request({
                "function": "COMMODITIES",
                "interval": "daily",
                "datatype": "json",
            })
            # Alpha Vantage commodities endpoint returns multiple commodities
            # We need to parse for WTI and Brent
            if "data" in data:
                for item in data["data"]:
                    if item.get("name") == "WTI Crude Oil" or "WTI" in item.get("name", ""):
                        results.append(OilPrice(
                            benchmark="WTI",
                            value=Decimal(str(item.get("value", 0))),
                            currency="USD",
                            unit="per barrel",
                            timestamp=datetime.fromisoformat(item.get("date", datetime.now(timezone.utc).isoformat())),
                            source=DataSource.ALPHA_VANTAGE,
                            is_delayed=True,
                        ))
                    elif item.get("name") == "Brent Crude Oil" or "Brent" in item.get("name", ""):
                        results.append(OilPrice(
                            benchmark="BRENT",
                            value=Decimal(str(item.get("value", 0))),
                            currency="USD",
                            unit="per barrel",
                            timestamp=datetime.fromisoformat(item.get("date", datetime.now(timezone.utc).isoformat())),
                            source=DataSource.ALPHA_VANTAGE,
                            is_delayed=True,
                        ))
        except Exception as e:
            raise DataSourceError(f"Failed to fetch oil prices: {e}", self.name)

        return results

    # Alternative: Use WTI and BRENT specific endpoints if available
    async def get_wti_price(self) -> Optional[OilPrice]:
        """Get WTI crude oil price."""
        try:
            data = await self._request({
                "function": "WTI",
                "interval": "daily",
            })
            if "data" in data and data["data"]:
                latest = data["data"][0]
                return OilPrice(
                    benchmark="WTI",
                    value=Decimal(str(latest.get("value", 0))),
                    currency="USD",
                    unit="per barrel",
                    timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                    source=DataSource.ALPHA_VANTAGE,
                    is_delayed=True,
                )
        except Exception:
            pass
        return None

    async def get_brent_price(self) -> Optional[OilPrice]:
        """Get Brent crude oil price."""
        try:
            data = await self._request({
                "function": "BRENT",
                "interval": "daily",
            })
            if "data" in data and data["data"]:
                latest = data["data"][0]
                return OilPrice(
                    benchmark="BRENT",
                    value=Decimal(str(latest.get("value", 0))),
                    currency="USD",
                    unit="per barrel",
                    timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                    source=DataSource.ALPHA_VANTAGE,
                    is_delayed=True,
                )
        except Exception:
            pass
        return None

    # =========================================================================
    # BOND YIELDS - US TREASURY
    # =========================================================================
    async def get_treasury_yields(self) -> List[BondYield]:
        """Get US Treasury yields (2Y, 10Y, Fed Funds Rate)."""
        results = []
        yield_map = {
            "2Y": 2,
            "10Y": 10,
        }

        for symbol, maturity in yield_map.items():
            try:
                data = await self._request({
                    "function": "TREASURY_YIELD",
                    "interval": "daily",
                    "maturity": symbol,
                })
                if "data" in data and data["data"]:
                    latest = data["data"][0]
                    results.append(BondYield(
                        country="US",
                        maturity_years=maturity,
                        value=Decimal(str(latest.get("value", 0))),
                        currency="USD",
                        unit="percent",
                        timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                        source=DataSource.ALPHA_VANTAGE,
                        is_delayed=True,
                    ))
            except Exception:
                continue

        # Fed Funds Rate
        try:
            data = await self._request({
                "function": "FEDERAL_FUNDS_RATE",
                "interval": "daily",
            })
            if "data" in data and data["data"]:
                latest = data["data"][0]
                results.append(BondYield(
                    country="US",
                    maturity_years=0,  # Overnight rate
                    value=Decimal(str(latest.get("value", 0))),
                    currency="USD",
                    unit="percent",
                    timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                    source=DataSource.ALPHA_VANTAGE,
                    is_delayed=True,
                    metadata={"type": "federal_funds_rate"},
                ))
        except Exception:
            pass

        return results

    # =========================================================================
    # STOCK INDICES
    # =========================================================================
    async def get_stock_indices(self) -> List[StockIndex]:
        """Get major stock indices."""
        results = []
        index_map = {
            "SPX": "S&P 500",
            "DJI": "Dow Jones Industrial Average",
            "COMP": "Nasdaq Composite",
            "NDX": "Nasdaq 100",
            "TSX": "S&P/TSX Composite",
            "STOXX50E": "Euro Stoxx 50",
            "FCHI": "CAC 40",
            "FTSE": "FTSE 100",
            "N225": "Nikkei 225",
            "HSI": "Hang Seng Index",
        }

        for symbol, name in index_map.items():
            try:
                data = await self._request({
                    "function": "INDEX_DATA",
                    "symbol": symbol,
                    "interval": "daily",
                })
                if "data" in data and data["data"]:
                    latest = data["data"][0]
                    results.append(StockIndex(
                        index_name=name,
                        value=Decimal(str(latest.get("value", 0))),
                        currency="USD" if "TSX" not in name and "FTSE" not in name and "STOXX" not in name and "FCHI" not in name and "N225" not in name and "HSI" not in name else "LOCAL",
                        unit="points",
                        timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                        source=DataSource.ALPHA_VANTAGE,
                        is_delayed=True,
                    ))
            except Exception:
                continue

        return results

    # =========================================================================
    # FOREX
    # =========================================================================
    async def get_forex_rates(self) -> List[ForexRate]:
        """Get major forex rates."""
        results = []
        pairs = [
            ("USD", "CAD"),
            ("EUR", "CAD"),
            ("USD", "MAD"),
            ("EUR", "USD"),
        ]

        for from_curr, to_curr in pairs:
            try:
                data = await self._request({
                    "function": "CURRENCY_EXCHANGE_RATE",
                    "from_currency": from_curr,
                    "to_currency": to_curr,
                })
                if "Realtime Currency Exchange Rate" in data:
                    rate_data = data["Realtime Currency Exchange Rate"]
                    results.append(ForexRate(
                        base_currency=from_curr,
                        quote_currency=to_curr,
                        value=Decimal(str(rate_data.get("5. Exchange Rate", 0))),
                        currency=to_curr,
                        unit=f"{from_curr}/{to_curr}",
                        timestamp=datetime.fromisoformat(
                            rate_data.get("6. Last Refreshed", datetime.now(timezone.utc).isoformat()).replace(" ", "T")
                        ),
                        source=DataSource.ALPHA_VANTAGE,
                        is_live=True,
                    ))
            except Exception:
                continue

        return results

    # =========================================================================
    # CRYPTO
    # =========================================================================
    async def get_crypto_prices(self) -> List[CryptoPrice]:
        """Get crypto prices (BTC, ETH)."""
        results = []
        symbols = ["BTC", "ETH"]

        for symbol in symbols:
            try:
                data = await self._request({
                    "function": "DIGITAL_CURRENCY_DAILY",
                    "symbol": symbol,
                    "market": "USD",
                })
                if "Time Series (Digital Currency Daily)" in data:
                    ts = data["Time Series (Digital Currency Daily)"]
                    latest_date = sorted(ts.keys(), reverse=True)[0]
                    latest = ts[latest_date]
                    results.append(CryptoPrice(
                        symbol=symbol,
                        value=Decimal(str(latest.get("4a. close (USD)", 0))),
                        currency="USD",
                        unit="per coin",
                        timestamp=datetime.fromisoformat(f"{latest_date}T00:00:00"),
                        source=DataSource.ALPHA_VANTAGE,
                        is_delayed=True,
                        price_usd=Decimal(str(latest.get("4a. close (USD)", 0))),
                    ))
            except Exception:
                continue

        return results

    # =========================================================================
    # ECONOMIC INDICATORS
    # =========================================================================
    async def get_cpi(self) -> Optional[MarketDataPoint]:
        """Get US CPI inflation rate."""
        try:
            data = await self._request({
                "function": "CPI",
                "interval": "monthly",
            })
            if "data" in data and data["data"]:
                latest = data["data"][0]
                return MarketDataPoint(
                    value=Decimal(str(latest.get("value", 0))),
                    currency="USD",
                    unit="percent yoy",
                    timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                    source=DataSource.ALPHA_VANTAGE,
                    is_delayed=True,
                    metadata={"indicator": "CPI"},
                )
        except Exception:
            pass
        return None

    async def get_gdp(self) -> Optional[MarketDataPoint]:
        """Get US Real GDP."""
        try:
            data = await self._request({
                "function": "REAL_GDP",
                "interval": "quarterly",
            })
            if "data" in data and data["data"]:
                latest = data["data"][0]
                return MarketDataPoint(
                    value=Decimal(str(latest.get("value", 0))),
                    currency="USD",
                    unit="billions chained 2017 USD",
                    timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                    source=DataSource.ALPHA_VANTAGE,
                    is_delayed=True,
                    metadata={"indicator": "REAL_GDP"},
                )
        except Exception:
            pass
        return None

    async def get_unemployment(self) -> Optional[MarketDataPoint]:
        """Get US unemployment rate."""
        try:
            data = await self._request({
                "function": "UNEMPLOYMENT",
                "interval": "monthly",
            })
            if "data" in data and data["data"]:
                latest = data["data"][0]
                return MarketDataPoint(
                    value=Decimal(str(latest.get("value", 0))),
                    currency="USD",
                    unit="percent",
                    timestamp=datetime.fromisoformat(latest.get("date", datetime.now(timezone.utc).isoformat())),
                    source=DataSource.ALPHA_VANTAGE,
                    is_delayed=True,
                    metadata={"indicator": "UNEMPLOYMENT"},
                )
        except Exception:
            pass
        return None