"""
CoinGecko API source for cryptocurrency prices.
Free tier: 10-30 requests/minute, no API key required for demo.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import CryptoPrice, DataSource


class CoinGeckoSource(DataSourceBase):
    """CoinGecko API client."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self):
        super().__init__(
            name="CoinGecko",
            base_url=self.BASE_URL,
            api_key=None,  # Free demo works without key
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
            await self._request("GET", "/ping")
            return True
        except Exception:
            return False

    async def get_crypto_prices(
        self,
        symbols: List[str] = None,
        vs_currencies: List[str] = None,
        include_24h_change: bool = True,
        include_24h_vol: bool = False,
        include_last_updated_at: bool = True,
    ) -> List[CryptoPrice]:
        """Get crypto prices for specified symbols."""
        if symbols is None:
            symbols = ["bitcoin", "ethereum"]
        if vs_currencies is None:
            vs_currencies = ["usd", "cad"]

        ids = ",".join(symbols)
        vs = ",".join(vs_currencies)

        params = {
            "ids": ids,
            "vs_currencies": vs,
            "include_24hr_change": str(include_24h_change).lower(),
            "include_24hr_vol": str(include_24h_vol).lower(),
            "include_last_updated_at": str(include_last_updated_at).lower(),
        }

        try:
            data = await self._request("GET", "/simple/price", params=params)
            results = []

            for symbol in symbols:
                if symbol not in data:
                    continue

                coin_data = data[symbol]
                price_usd = coin_data.get("usd")
                price_cad = coin_data.get("cad")
                change_24h = coin_data.get("usd_24h_change")

                # Map coin IDs to symbols
                symbol_map = {"bitcoin": "BTC", "ethereum": "ETH"}
                display_symbol = symbol_map.get(symbol, symbol.upper())

                results.append(CryptoPrice(
                    symbol=display_symbol,
                    value=Decimal(str(price_usd)) if price_usd else Decimal("0"),
                    currency="USD",
                    unit="per coin",
                    timestamp=datetime.now(timezone.utc),
                    source=DataSource.COINGECKO,
                    is_live=True,
                    price_usd=Decimal(str(price_usd)) if price_usd else None,
                    price_cad=Decimal(str(price_cad)) if price_cad else None,
                    change_24h_pct=Decimal(str(change_24h)) if change_24h else None,
                ))

            return results

        except Exception as e:
            raise DataSourceError(f"Failed to fetch crypto prices: {e}", self.name)

    async def get_market_data(self, coin_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Get detailed market data including market cap, volume, etc."""
        if coin_ids is None:
            coin_ids = ["bitcoin", "ethereum"]

        ids = ",".join(coin_ids)

        params = {
            "ids": ids,
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": len(coin_ids),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d",
        }

        try:
            data = await self._request("GET", "/coins/markets", params=params)
            return data
        except Exception as e:
            raise DataSourceError(f"Failed to fetch market data: {e}", self.name)

    async def get_trending(self) -> List[Dict[str, Any]]:
        """Get trending coins."""
        try:
            data = await self._request("GET", "/search/trending")
            return data.get("coins", [])
        except Exception as e:
            raise DataSourceError(f"Failed to fetch trending: {e}", self.name)

    async def get_global_data(self) -> Dict[str, Any]:
        """Get global crypto market data."""
        try:
            data = await self._request("GET", "/global")
            return data.get("data", {})
        except Exception as e:
            raise DataSourceError(f"Failed to fetch global data: {e}", self.name)