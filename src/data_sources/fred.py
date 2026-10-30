"""
FRED (Federal Reserve Economic Data) API source for US economic data.
Free tier: 120 requests/minute, requires API key.
Coverage: US interest rates, inflation, employment, GDP, Treasury yields, etc.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import BondYield, DataSource, MarketDataPoint


class FredSource(DataSourceBase):
    """FRED API client for US economic data."""

    BASE_URL = "https://api.stlouisfed.org/fred"

    # Key FRED series IDs for our briefing
    SERIES = {
        # Interest Rates
        "FEDFUNDS": ("US", 0, "Federal Funds Rate (Effective)"),
        "DFEDTARU": ("US", 0, "Federal Funds Target Rate (Upper)"),
        "DFEDTARL": ("US", 0, "Federal Funds Target Rate (Lower)"),
        "DGS2": ("US", 2, "2-Year Treasury Constant Maturity Rate"),
        "DGS5": ("US", 5, "5-Year Treasury Constant Maturity Rate"),
        "DGS10": ("US", 10, "10-Year Treasury Constant Maturity Rate"),
        "DGS30": ("US", 30, "30-Year Treasury Constant Maturity Rate"),
        "T10Y2Y": ("US", 0, "10-Year minus 2-Year Treasury Spread"),
        "T10Y3M": ("US", 0, "10-Year minus 3-Month Treasury Spread"),

        # Inflation
        "CPIAUCSL": ("US", 0, "CPI All Items (YoY %)"),
        "CPILFESL": ("US", 0, "Core CPI (YoY %)"),
        "PCEPI": ("US", 0, "PCE Price Index (YoY %)"),
        "PCEPILFE": ("US", 0, "Core PCE Price Index (YoY %)"),

        # Employment
        "UNRATE": ("US", 0, "Unemployment Rate"),
        "PAYEMS": ("US", 0, "Total Nonfarm Payrolls"),
        "CIVPART": ("US", 0, "Labor Force Participation Rate"),
        "EMRATIO": ("US", 0, "Employment-Population Ratio"),

        # GDP & Growth
        "GDP": ("US", 0, "Real GDP (QoQ Annualized %)"),
        "GDPC1": ("US", 0, "Real GDP (Billions Chained 2017 $)"),

        # Housing
        "HOUST": ("US", 0, "Housing Starts"),
        "PERMIT": ("US", 0, "Building Permits"),
        "CSUSHPINSA": ("US", 0, "S&P/Case-Shiller Home Price Index"),

        # Money Supply
        "M1SL": ("US", 0, "M1 Money Supply"),
        "M2SL": ("US", 0, "M2 Money Supply"),

        # Dollar Index
        "DTWEXBGS": ("US", 0, "Broad Trade Weighted Dollar Index"),

        # Oil/Energy (from EIA via FRED)
        "DCOILWTICO": ("US", 0, "WTI Crude Oil Spot Price ($/bbl)"),
        "DCOILBRENTEU": ("US", 0, "Brent Crude Oil Spot Price ($/bbl)"),
    }

    def __init__(self):
        super().__init__(
            name="FRED",
            base_url=self.BASE_URL,
            api_key=settings.fred_api_key,
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
        limit: int = 1,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single series from FRED."""
        try:
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "limit": limit,
                "sort_order": "desc",
            }
            if start_date:
                params["observation_start"] = start_date
            if end_date:
                params["observation_end"] = end_date

            response = await self.client.get("/series/observations", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DataSourceError(f"Failed to fetch FRED series {series_id}: {e}", self.name)

    async def health_check(self) -> bool:
        """Check API availability."""
        try:
            await self._fetch_series("FEDFUNDS", limit=1)
            return True
        except Exception:
            return False

    def _parse_observation(self, obs: Dict, series_id: str) -> Optional[Dict]:
        """Parse a FRED observation."""
        value_str = obs.get("value")
        date_str = obs.get("date")
        if value_str and value_str != "." and date_str:
            try:
                return {
                    "value": Decimal(value_str),
                    "date": datetime.fromisoformat(f"{date_str}T00:00:00"),
                }
            except Exception:
                pass
        return None

    async def get_series_latest(self, series_id: str) -> Optional[Dict]:
        """Get latest observation for a series."""
        data = await self._fetch_series(series_id, limit=1)
        if data and "observations" in data and data["observations"]:
            return self._parse_observation(data["observations"][0], series_id)
        return None

    async def get_series_recent(self, series_id: str, count: int = 10) -> List[Dict]:
        """Get recent observations for a series."""
        data = await self._fetch_series(series_id, limit=count)
        if data and "observations" in data:
            results = []
            for obs in data["observations"]:
                parsed = self._parse_observation(obs, series_id)
                if parsed:
                    results.append(parsed)
            return results
        return []

    # =========================================================================
    # INTEREST RATES
    # =========================================================================
    async def get_fed_funds_rate(self) -> Optional[BondYield]:
        """Get Federal Funds Effective Rate."""
        try:
            data = await self.get_series_latest("FEDFUNDS")
            if data:
                return BondYield(
                    country="US",
                    maturity_years=0,
                    value=data["value"],
                    currency="USD",
                    unit="percent",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_delayed=True,
                    metadata={"type": "federal_funds_effective", "description": "Federal Funds Effective Rate"},
                )
        except Exception:
            pass
        return None

    async def get_fed_target_rate(self) -> Optional[BondYield]:
        """Get Federal Funds Target Rate (Upper bound)."""
        try:
            data = await self.get_series_latest("DFEDTARU")
            if data:
                return BondYield(
                    country="US",
                    maturity_years=0,
                    value=data["value"],
                    currency="USD",
                    unit="percent",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_delayed=True,
                    metadata={"type": "federal_funds_target_upper", "description": "Federal Funds Target Rate Upper Bound"},
                )
        except Exception:
            pass
        return None

    async def get_treasury_yields(self) -> List[BondYield]:
        """Get US Treasury yields (2Y, 5Y, 10Y, 30Y)."""
        results = []
        yield_series = {
            "DGS2": 2,
            "DGS5": 5,
            "DGS10": 10,
            "DGS30": 30,
        }

        for series_id, maturity in yield_series.items():
            try:
                data = await self.get_series_latest(series_id)
                if data:
                    results.append(BondYield(
                        country="US",
                        maturity_years=maturity,
                        value=data["value"],
                        currency="USD",
                        unit="percent",
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata={"series_id": series_id, "description": self.SERIES[series_id][2]},
                    ))
            except Exception:
                continue

        return results

    async def get_yield_spreads(self) -> List[MarketDataPoint]:
        """Get key yield curve spreads."""
        results = []
        spread_series = {
            "T10Y2Y": "10Y-2Y Spread",
            "T10Y3M": "10Y-3M Spread",
        }

        for series_id, description in spread_series.items():
            try:
                data = await self.get_series_latest(series_id)
                if data:
                    results.append(MarketDataPoint(
                        value=data["value"],
                        currency="USD",
                        unit="percent",
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata={"spread": description, "series_id": series_id},
                    ))
            except Exception:
                continue

        return results

    # =========================================================================
    # INFLATION
    # =========================================================================
    async def get_inflation_data(self) -> Dict[str, Optional[MarketDataPoint]]:
        """Get key inflation indicators."""
        results = {}
        inflation_series = {
            "CPIAUCSL": "CPI YoY",
            "CPILFESL": "Core CPI YoY",
            "PCEPI": "PCE YoY",
            "PCEPILFE": "Core PCE YoY",
        }

        for series_id, description in inflation_series.items():
            try:
                data = await self.get_series_latest(series_id)
                if data:
                    results[series_id] = MarketDataPoint(
                        value=data["value"],
                        currency="USD",
                        unit="percent yoy",
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata={"indicator": description, "series_id": series_id},
                    )
            except Exception:
                results[series_id] = None

        return results

    # =========================================================================
    # EMPLOYMENT
    # =========================================================================
    async def get_employment_data(self) -> Dict[str, Optional[MarketDataPoint]]:
        """Get key employment indicators."""
        results = {}
        employment_series = {
            "UNRATE": "Unemployment Rate",
            "PAYEMS": "Nonfarm Payrolls",
            "CIVPART": "Labor Force Participation",
            "EMRATIO": "Employment-Population Ratio",
        }

        for series_id, description in employment_series.items():
            try:
                data = await self.get_series_latest(series_id)
                if data:
                    unit = "percent" if series_id in ["UNRATE", "CIVPART", "EMRATIO"] else "thousands"
                    results[series_id] = MarketDataPoint(
                        value=data["value"],
                        currency="USD",
                        unit=unit,
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata={"indicator": description, "series_id": series_id},
                    )
            except Exception:
                results[series_id] = None

        return results

    # =========================================================================
    # GDP & HOUSING
    # =========================================================================
    async def get_gdp(self) -> Optional[MarketDataPoint]:
        """Get Real GDP growth."""
        try:
            data = await self.get_series_latest("GDP")
            if data:
                return MarketDataPoint(
                    value=data["value"],
                    currency="USD",
                    unit="percent qoq annualized",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_delayed=True,
                    metadata={"indicator": "Real GDP QoQ", "series_id": "GDP"},
                )
        except Exception:
            pass
        return None

    async def get_housing_data(self) -> Dict[str, Optional[MarketDataPoint]]:
        """Get housing indicators."""
        results = {}
        housing_series = {
            "HOUST": "Housing Starts",
            "PERMIT": "Building Permits",
            "CSUSHPINSA": "Case-Shiller Home Price Index",
        }

        for series_id, description in housing_series.items():
            try:
                data = await self.get_series_latest(series_id)
                if data:
                    unit = "thousands" if series_id in ["HOUST", "PERMIT"] else "index"
                    results[series_id] = MarketDataPoint(
                        value=data["value"],
                        currency="USD",
                        unit=unit,
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata={"indicator": description, "series_id": series_id},
                    )
            except Exception:
                results[series_id] = None

        return results

    # =========================================================================
    # OIL PRICES (from FRED/EIA)
    # =========================================================================
    async def get_oil_prices(self) -> List[MarketDataPoint]:
        """Get WTI and Brent oil prices from FRED."""
        results = []
        oil_series = {
            "DCOILWTICO": "WTI Crude Oil",
            "DCOILBRENTEU": "Brent Crude Oil",
        }

        for series_id, description in oil_series.items():
            try:
                data = await self.get_series_latest(series_id)
                if data:
                    results.append(MarketDataPoint(
                        value=data["value"],
                        currency="USD",
                        unit="per barrel",
                        timestamp=data["date"],
                        source=DataSource.FRED,
                        is_delayed=True,
                        metadata={"benchmark": description, "series_id": series_id},
                    ))
            except Exception:
                continue

        return results

    # =========================================================================
    # DOLLAR INDEX
    # =========================================================================
    async def get_dollar_index(self) -> Optional[MarketDataPoint]:
        """Get Trade Weighted Dollar Index."""
        try:
            data = await self.get_series_latest("DTWEXBGS")
            if data:
                return MarketDataPoint(
                    value=data["value"],
                    currency="USD",
                    unit="index",
                    timestamp=data["date"],
                    source=DataSource.FRED,
                    is_delayed=True,
                    metadata={"indicator": "Broad Dollar Index", "series_id": "DTWEXBGS"},
                )
        except Exception:
            pass
        return None

    # =========================================================================
    # COMPREHENSIVE DATA
    # =========================================================================
    async def get_all_us_economic_data(self) -> Dict[str, Any]:
        """Fetch all US economic data in parallel."""
        import asyncio

        results = await asyncio.gather(
            self.get_fed_funds_rate(),
            self.get_fed_target_rate(),
            self.get_treasury_yields(),
            self.get_yield_spreads(),
            self.get_inflation_data(),
            self.get_employment_data(),
            self.get_gdp(),
            self.get_housing_data(),
            self.get_oil_prices(),
            self.get_dollar_index(),
            return_exceptions=True,
        )

        return {
            "fed_funds_effective": results[0] if not isinstance(results[0], Exception) else None,
            "fed_target_rate": results[1] if not isinstance(results[1], Exception) else None,
            "treasury_yields": results[2] if not isinstance(results[2], Exception) else [],
            "yield_spreads": results[3] if not isinstance(results[3], Exception) else [],
            "inflation": results[4] if not isinstance(results[4], Exception) else {},
            "employment": results[5] if not isinstance(results[5], Exception) else {},
            "gdp": results[6] if not isinstance(results[6], Exception) else None,
            "housing": results[7] if not isinstance(results[7], Exception) else {},
            "oil_prices": results[8] if not isinstance(results[8], Exception) else [],
            "dollar_index": results[9] if not isinstance(results[9], Exception) else None,
            "errors": [str(r) for r in results if isinstance(r, Exception)],
        }