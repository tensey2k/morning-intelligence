"""
Bank of Canada Valet API source for Canadian bond yields and policy rate.
Free, no API key required.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import BondYield, DataSource, MarketDataPoint


class BankOfCanadaSource(DataSourceBase):
    """Bank of Canada Valet API client."""

    BASE_URL = "https://www.bankofcanada.ca/valet/observations"

    # Series IDs from BoC Valet API
    SERIES = {
        # Benchmark bond yields
        "BD.CDN.2YR.DQ.YLD": ("CA", 2, "Benchmark Bond Yield, 2-Year"),
        "BD.CDN.3YR.DQ.YLD": ("CA", 3, "Benchmark Bond Yield, 3-Year"),
        "BD.CDN.5YR.DQ.YLD": ("CA", 5, "Benchmark Bond Yield, 5-Year"),
        "BD.CDN.7YR.DQ.YLD": ("CA", 7, "Benchmark Bond Yield, 7-Year"),
        "BD.CDN.10YR.DQ.YLD": ("CA", 10, "Benchmark Bond Yield, 10-Year"),
        "BD.CDN.LONG.DQ.YLD": ("CA", 30, "Benchmark Bond Yield, Long-Term"),
        "BD.CDN.RRB.DQ.YLD": ("CA", 0, "Real Return Bond Yield"),

        # Policy rate
        "B114039": ("CA", 0, "Target for the Overnight Rate (Policy Rate)"),

        # Money market rates
        "AVG.INTWO": ("CA", 0, "CORRA - Canadian Overnight Repo Rate Average"),
        "BA.CDN.30D.MID": ("CA", 0, "Bankers' Acceptance 30-Day"),
        "BA.CDN.90D.MID": ("CA", 0, "Bankers' Acceptance 90-Day"),

        # Exchange rates
        "FXUSDCAD": ("USD", 0, "USD/CAD Daily Average"),
        "FXEURCAD": ("EUR", 0, "EUR/CAD Daily Average"),
        "FXGBPCAD": ("GBP", 0, "GBP/CAD Daily Average"),
        "FXAUDCAD": ("AUD", 0, "AUD/CAD Daily Average"),

        # Inflation
        "ATOM_V41693242": ("CA", 0, "CPIX Year-over-Year"),
    }

    def __init__(self):
        super().__init__(
            name="Bank of Canada Valet",
            base_url=self.BASE_URL,
            api_key=None,  # No API key needed
            timeout=30.0,
            max_retries=3,
        )

    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "MorningIntelligence/1.0",
            "Accept": "application/json",
        }

    async def _fetch_series(self, series_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single series from BoC Valet."""
        try:
            url = f"{self.base_url}/{series_id}/json"
            params = {"recent": 5}  # Get last 5 observations
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DataSourceError(f"Failed to fetch series {series_id}: {e}", self.name)

    async def health_check(self) -> bool:
        """Check API availability."""
        try:
            await self._fetch_series("FXUSDCAD")
            return True
        except Exception:
            return False

    async def get_bond_yields(self) -> List[BondYield]:
        """Get Canadian government bond yields."""
        results = []
        bond_series = {
            k: v for k, v in self.SERIES.items()
            if k.startswith("BD.CDN") and "YLD" in k
        }

        for series_id, (country, maturity, description) in bond_series.items():
            try:
                data = await self._fetch_series(series_id)
                if data and "observations" in data:
                    obs = data["observations"]
                    if obs:
                        latest = obs[-1]
                        value_str = latest.get(series_id, {}).get("v")
                        date_str = latest.get("d")
                        if value_str and value_str != "null":
                            results.append(BondYield(
                                country=country,
                                maturity_years=maturity,
                                value=Decimal(value_str),
                                currency="CAD",
                                unit="percent",
                                timestamp=datetime.fromisoformat(f"{date_str}T00:00:00"),
                                source=DataSource.BANK_OF_CANADA,
                                is_delayed=True,
                                metadata={"description": description, "series_id": series_id},
                            ))
            except Exception:
                continue

        return results

    async def get_policy_rate(self) -> Optional[BondYield]:
        """Get Bank of Canada policy rate (target overnight rate)."""
        try:
            data = await self._fetch_series("B114039")
            if data and "observations" in data:
                obs = data["observations"]
                if obs:
                    latest = obs[-1]
                    value_str = latest.get("B114039", {}).get("v")
                    date_str = latest.get("d")
                    if value_str and value_str != "null":
                        return BondYield(
                            country="CA",
                            maturity_years=0,
                            value=Decimal(value_str),
                            currency="CAD",
                            unit="percent",
                            timestamp=datetime.fromisoformat(f"{date_str}T00:00:00"),
                            source=DataSource.BANK_OF_CANADA,
                            is_delayed=True,
                            metadata={"type": "policy_rate", "description": "Target for the Overnight Rate"},
                        )
        except Exception:
            pass
        return None

    async def get_money_market_rates(self) -> List[MarketDataPoint]:
        """Get CORRA and Bankers' Acceptances."""
        results = []
        mm_series = {k: v for k, v in self.SERIES.items() if k.startswith("AVG.") or k.startswith("BA.")}

        for series_id, (country, maturity, description) in mm_series.items():
            try:
                data = await self._fetch_series(series_id)
                if data and "observations" in data:
                    obs = data["observations"]
                    if obs:
                        latest = obs[-1]
                        value_str = latest.get(series_id, {}).get("v")
                        date_str = latest.get("d")
                        if value_str and value_str != "null":
                            results.append(MarketDataPoint(
                                value=Decimal(value_str),
                                currency="CAD",
                                unit="percent",
                                timestamp=datetime.fromisoformat(f"{date_str}T00:00:00"),
                                source=DataSource.BANK_OF_CANADA,
                                is_delayed=True,
                                metadata={"description": description, "series_id": series_id},
                            ))
            except Exception:
                continue

        return results

    async def get_exchange_rates(self) -> List[MarketDataPoint]:
        """Get CAD exchange rates."""
        results = []
        fx_series = {k: v for k, v in self.SERIES.items() if k.startswith("FX")}

        for series_id, (base_currency, maturity, description) in fx_series.items():
            try:
                data = await self._fetch_series(series_id)
                if data and "observations" in data:
                    obs = data["observations"]
                    if obs:
                        latest = obs[-1]
                        value_str = latest.get(series_id, {}).get("v")
                        date_str = latest.get("d")
                        if value_str and value_str != "null":
                            quote_currency = series_id.replace("FX", "").replace("CAD", "")
                            results.append(MarketDataPoint(
                                value=Decimal(value_str),
                                currency="CAD",
                                unit=f"{base_currency}/CAD",
                                timestamp=datetime.fromisoformat(f"{date_str}T00:00:00"),
                                source=DataSource.BANK_OF_CANADA,
                                is_delayed=True,
                                metadata={"base_currency": base_currency, "description": description, "series_id": series_id},
                            ))
            except Exception:
                continue

        return results

    async def get_cpi(self) -> Optional[MarketDataPoint]:
        """Get Canadian CPI inflation."""
        try:
            data = await self._fetch_series("ATOM_V41693242")
            if data and "observations" in data:
                obs = data["observations"]
                if obs:
                    latest = obs[-1]
                    value_str = latest.get("ATOM_V41693242", {}).get("v")
                    date_str = latest.get("d")
                    if value_str and value_str != "null":
                        return MarketDataPoint(
                            value=Decimal(value_str),
                            currency="CAD",
                            unit="percent yoy",
                            timestamp=datetime.fromisoformat(f"{date_str}T00:00:00"),
                            source=DataSource.BANK_OF_CANADA,
                            is_delayed=True,
                            metadata={"indicator": "CPIX", "description": "CPIX Year-over-Year"},
                        )
        except Exception:
            pass
        return None

    async def get_all_canadian_data(self) -> Dict[str, Any]:
        """Fetch all Canadian market data in one call."""
        return {
            "bond_yields": await self.get_bond_yields(),
            "policy_rate": await self.get_policy_rate(),
            "money_market": await self.get_money_market_rates(),
            "exchange_rates": await self.get_exchange_rates(),
            "cpi": await self.get_cpi(),
        }