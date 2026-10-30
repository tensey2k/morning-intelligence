"""
EIA (U.S. Energy Information Administration) API source for oil and energy data.
Free tier: Unlimited requests with API key.
Coverage: WTI/Brent crude, gasoline, diesel, inventories, production, etc.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import DataSource, MarketDataPoint, OilPrice


class EIASource(DataSourceBase):
    """EIA API client for oil and energy data."""

    BASE_URL = "https://api.eia.gov/v2"

    # Key EIA series for oil prices and inventory
    SERIES = {
        # Crude Oil Prices
        "PET.RWTC.D": ("WTI", "Cushing OK WTI Spot Price FOB ($/bbl)"),
        "PET.RBRTE.D": ("BRENT", "Europe Brent Spot Price FOB ($/bbl)"),
        "PET.RDHD.D": ("DUBAI", "Dubai Crude Oil Spot Price ($/bbl)"),

        # Refined Products
        "PET.EER_EPMRU_PF4_RGC_DPG.D": ("GASOLINE", "US Gulf Coast Regular Gasoline Price ($/gal)"),
        "PET.EER_EPD2F_PF4_RGC_DPG.D": ("DIESEL", "US Gulf Coast Ultra Low Sulfur Diesel Price ($/gal)"),
        "PET.EER_EPJK_PF4_RGC_DPG.D": ("JET_FUEL", "US Gulf Coast Kerosene-Type Jet Fuel Price ($/gal)"),

        # Weekly Inventory (Wednesday release)
        "PET.WCRSTUS1.W": ("CRUDE_INV", "US Crude Oil Inventories (million barrels)"),
        "PET.WGESTUS1.W": ("GASOLINE_INV", "US Gasoline Inventories (million barrels)"),
        "PET.WDISTUS1.W": ("DISTILLATE_INV", "US Distillate Inventories (million barrels)"),
        "PET.WJESTUS1.W": ("JET_INV", "US Jet Fuel Inventories (million barrels)"),
        "PET.W_CST_US.W": ("CUSHING_INV", "Cushing OK Crude Oil Inventories (million barrels)"),
        "PET.W_EPC0_SAX_YCUOK_MBBL.W": ("SPR_INV", "Strategic Petroleum Reserve (million barrels)"),

        # Production
        "PET.WCRFPUS2.W": ("US_PRODUCTION", "US Crude Oil Field Production (million bpd)"),
        "PET.MCRFPUS2.M": ("US_PRODUCTION_MONTHLY", "US Crude Oil Production Monthly (million bpd)"),

        # Imports/Exports
        "PET.WCRNTUS1.W": ("NET_IMPORTS", "US Net Crude Oil Imports (million bpd)"),
        "PET.W_EPLLPA_NUS_DPG.W": ("GASOLINE_IMPORTS", "US Gasoline Imports (million bpd)"),
    }

    def __init__(self):
        super().__init__(
            name="EIA",
            base_url=self.BASE_URL,
            api_key=settings.eia_api_key,
            timeout=30.0,
            max_retries=3,
        )

    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "MorningIntelligence/1.0",
            "Accept": "application/json",
        }

    async def _fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        length: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single series from EIA."""
        try:
            params = {
                "api_key": self.api_key,
                "frequency": "daily" if ".D" in series_id else "weekly" if ".W" in series_id else "monthly",
                "data[0]": "value",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "offset": 0,
                "length": length,
            }
            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date

            # EIA v2 API format: /series/route
            # Series ID format: PET.RWTC.D -> route: petroleum/pri/spt
            route = self._get_route(series_id)
            response = await self.client.get(f"/{route}", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DataSourceError(f"Failed to fetch EIA series {series_id}: {e}", self.name)

    def _get_route(self, series_id: str) -> str:
        """Map series ID to EIA API route."""
        # EIA v2 routes
        if series_id.startswith("PET.RWTC") or series_id.startswith("PET.RBRTE") or series_id.startswith("PET.RDHD"):
            return "petroleum/pri/spt/data"
        elif series_id.startswith("PET.EER"):
            return "petroleum/pri/ref/data"
        elif series_id.startswith("PET.WCRST") or series_id.startswith("PET.WGEST") or series_id.startswith("PET.WDIST") or series_id.startswith("PET.WJEST") or series_id.startswith("PET.W_CST") or series_id.startswith("PET.W_EPC0"):
            return "petroleum/stoc/wstk/data"
        elif series_id.startswith("PET.WCRFP") or series_id.startswith("PET.MCRFP"):
            return "petroleum/crdp/crpdn/data"
        elif series_id.startswith("PET.WCRNT") or series_id.startswith("PET.W_EPLLPA"):
            return "petroleum/trade/imp/data"
        else:
            return "petroleum/pri/spt/data"  # default

    async def health_check(self) -> bool:
        """Check API availability."""
        try:
            await self._fetch_series("PET.RWTC.D", length=1)
            return True
        except Exception:
            return False

    def _parse_response(self, data: Dict, series_id: str) -> List[Dict]:
        """Parse EIA API response."""
        results = []
        if "response" in data and "data" in data["response"]:
            for item in data["response"]["data"]:
                value = item.get("value")
                period = item.get("period")
                if value is not None and period:
                    try:
                        # Parse period (format: YYYY-MM-DD or YYYY-MM or YYYY-WW)
                        if len(period) == 10:  # YYYY-MM-DD
                            dt = datetime.fromisoformat(f"{period}T00:00:00")
                        elif len(period) == 7:  # YYYY-MM
                            dt = datetime.fromisoformat(f"{period}-01T00:00:00")
                        elif "W" in period:  # YYYY-WW
                            year, week = period.split("-W")
                            # Approximate: first day of week
                            dt = datetime.strptime(f"{year}-W{int(week):02d}-1", "%G-W%V-%u")
                        else:
                            dt = datetime.now(timezone.utc)

                        results.append({
                            "value": Decimal(str(value)),
                            "date": dt,
                            "period": period,
                        })
                    except Exception:
                        continue
        return results

    async def get_latest(self, series_id: str) -> Optional[Dict]:
        """Get latest observation for a series."""
        data = await self._fetch_series(series_id, length=5)
        parsed = self._parse_response(data, series_id)
        return parsed[0] if parsed else None

    # =========================================================================
    # CRUDE OIL PRICES
    # =========================================================================
    async def get_wti_price(self) -> Optional[OilPrice]:
        """Get WTI crude oil spot price."""
        try:
            data = await self.get_latest("PET.RWTC.D")
            if data:
                return OilPrice(
                    benchmark="WTI",
                    value=data["value"],
                    currency="USD",
                    unit="per barrel",
                    timestamp=data["date"],
                    source=DataSource.FRED,  # Using FRED enum since EIA not in enum
                    is_live=False,
                    is_delayed=True,
                    delay_minutes=1440,  # Daily data, ~24h delay
                    metadata={"source": "EIA", "series": "PET.RWTC.D", "description": "Cushing OK WTI Spot Price FOB"},
                )
        except Exception:
            pass
        return None

    async def get_brent_price(self) -> Optional[OilPrice]:
        """Get Brent crude oil spot price."""
        try:
            data = await self.get_latest("PET.RBRTE.D")
            if data:
                return OilPrice(
                    benchmark="BRENT",
                    value=data["value"],
                    currency="USD",
                    unit="per barrel",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_live=False,
                    is_delayed=True,
                    delay_minutes=1440,
                    metadata={"source": "EIA", "series": "PET.RBRTE.D", "description": "Europe Brent Spot Price FOB"},
                )
        except Exception:
            pass
        return None

    async def get_dubai_price(self) -> Optional[OilPrice]:
        """Get Dubai crude oil spot price."""
        try:
            data = await self.get_latest("PET.RDHD.D")
            if data:
                return OilPrice(
                    benchmark="DUBAI",
                    value=data["value"],
                    currency="USD",
                    unit="per barrel",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_live=False,
                    is_delayed=True,
                    delay_minutes=1440,
                    metadata={"source": "EIA", "series": "PET.RDHD.D", "description": "Dubai Crude Oil Spot Price"},
                )
        except Exception:
            pass
        return None

    async def get_all_crude_prices(self) -> List[OilPrice]:
        """Get all crude oil benchmarks."""
        import asyncio
        results = await asyncio.gather(
            self.get_wti_price(),
            self.get_brent_price(),
            self.get_dubai_price(),
            return_exceptions=True,
        )
        return [r for r in results if r and not isinstance(r, Exception)]

    # =========================================================================
    # REFINED PRODUCTS
    # =========================================================================
    async def get_refined_products(self) -> List[MarketDataPoint]:
        """Get gasoline, diesel, jet fuel prices."""
        results = []
        products = {
            "PET.EER_EPMRU_PF4_RGC_DPG.D": ("GASOLINE", "US Gulf Coast Regular Gasoline"),
            "PET.EER_EPD2F_PF4_RGC_DPG.D": ("DIESEL", "US Gulf Coast ULSD"),
            "PET.EER_EPJK_PF4_RGC_DPG.D": ("JET_FUEL", "US Gulf Coast Jet Fuel"),
        }

        for series_id, (product, description) in products.items():
            try:
                data = await self.get_latest(series_id)
                if data:
                    results.append(MarketDataPoint(
                        value=data["value"],
                        currency="USD",
                        unit="per gallon",
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata={"product": product, "description": description, "series": series_id},
                    ))
            except Exception:
                continue

        return results

    # =========================================================================
    # WEEKLY INVENTORIES (Critical for oil market analysis)
    # =========================================================================
    async def get_weekly_inventories(self) -> List[MarketDataPoint]:
        """Get weekly inventory data (released Wednesdays)."""
        results = []
        inventory_series = {
            "PET.WCRSTUS1.W": ("CRUDE_INV", "US Crude Oil Inventories"),
            "PET.WGESTUS1.W": ("GASOLINE_INV", "US Gasoline Inventories"),
            "PET.WDISTUS1.W": ("DISTILLATE_INV", "US Distillate Inventories"),
            "PET.WJESTUS1.W": ("JET_INV", "US Jet Fuel Inventories"),
            "PET.W_CST_US.W": ("CUSHING_INV", "Cushing OK Inventories"),
            "PET.W_EPC0_SAX_YCUOK_MBBL.W": ("SPR_INV", "Strategic Petroleum Reserve"),
        }

        for series_id, (inv_type, description) in inventory_series.items():
            try:
                data = await self.get_latest(series_id)
                if data:
                    # Get previous week for change calculation
                    prev_data = await self._fetch_series(series_id, length=2)
                    prev_parsed = self._parse_response(prev_data, series_id)
                    change = None
                    change_pct = None
                    if len(prev_parsed) >= 2:
                        change = prev_parsed[0]["value"] - prev_parsed[1]["value"]
                        if prev_parsed[1]["value"] != 0:
                            change_pct = (change / prev_parsed[1]["value"]) * 100

                    results.append(MarketDataPoint(
                        value=data["value"],
                        currency="USD",
                        unit="million barrels",
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        delay_minutes=10080,  # Weekly data, ~1 week delay
                        change_24h=change,
                        change_24h_pct=change_pct,
                        metadata={"inventory_type": inv_type, "description": description, "series": series_id},
                    ))
            except Exception:
                continue

        return results

    # =========================================================================
    # PRODUCTION & TRADE
    # =========================================================================
    async def get_us_production(self) -> Optional[MarketDataPoint]:
        """Get US crude oil production."""
        try:
            data = await self.get_latest("PET.WCRFPUS2.W")
            if data:
                return MarketDataPoint(
                    value=data["value"],
                    currency="USD",
                    unit="million bpd",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_delayed=True,
                    metadata={"indicator": "US Crude Production", "series": "PET.WCRFPUS2.W"},
                )
        except Exception:
            pass
        return None

    async def get_net_imports(self) -> Optional[MarketDataPoint]:
        """Get US net crude oil imports."""
        try:
            data = await self.get_latest("PET.WCRNTUS1.W")
            if data:
                return MarketDataPoint(
                    value=data["value"],
                    currency="USD",
                    unit="million bpd",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_delayed=True,
                    metadata={"indicator": "US Net Crude Imports", "series": "PET.WCRNTUS1.W"},
                )
        except Exception:
            pass
        return None

    # =========================================================================
    # COMPREHENSIVE OIL MARKET DATA
    # =========================================================================
    async def get_all_oil_market_data(self) -> Dict[str, Any]:
        """Fetch all oil market data in parallel."""
        import asyncio

        results = await asyncio.gather(
            self.get_all_crude_prices(),
            self.get_refined_products(),
            self.get_weekly_inventories(),
            self.get_us_production(),
            self.get_net_imports(),
            return_exceptions=True,
        )

        return {
            "crude_prices": results[0] if not isinstance(results[0], Exception) else [],
            "refined_products": results[1] if not isinstance(results[1], Exception) else [],
            "inventories": results[2] if not isinstance(results[2], Exception) else [],
            "production": results[3] if not isinstance(results[3], Exception) else None,
            "net_imports": results[4] if not isinstance(results[4], Exception) else None,
            "errors": [str(r) for r in results if isinstance(r, Exception)],
        }