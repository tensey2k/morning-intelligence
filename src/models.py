"""
Pydantic models for Morning Intelligence briefing content.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BriefingStatus(str, Enum):
    """Status of a briefing generation/delivery."""
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    FAILED = "failed"
    PARTIAL = "partial"


class DeliveryChannel(str, Enum):
    """Delivery channel."""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"


class DeliveryStatus(str, Enum):
    """Status of a delivery attempt."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class DataSource(str, Enum):
    """Source of market data."""
    ALPHA_VANTAGE = "alpha_vantage"
    BANK_OF_CANADA = "bank_of_canada"
    COINGECKO = "coingecko"
    OPEN_METEO = "open_meteo"
    FINANCE_CALENDAR = "finance_calendar"
    RSS_FEED = "rss_feed"
    TWELVE_DATA = "twelve_data"
    FRED = "fred"
    EIA = "eia"
    MARKETAUX = "marketaux"
    BANK_AL_MAGHRIB = "bank_al_maghrib"


class MarketDataPoint(BaseModel):
    """Single market data point with metadata."""
    model_config = ConfigDict(populate_by_name=True)

    value: Decimal
    currency: str = "USD"
    unit: str = ""
    timestamp: datetime
    source: DataSource
    is_live: bool = False
    is_delayed: bool = False
    delay_minutes: Optional[int] = None
    change_24h: Optional[Decimal] = None
    change_24h_pct: Optional[Decimal] = None
    change_weekly: Optional[Decimal] = None
    change_weekly_pct: Optional[Decimal] = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("value", "change_24h", "change_24h_pct", "change_weekly", "change_weekly_pct", mode="before")
    @classmethod
    def parse_decimal(cls, v: Any) -> Optional[Decimal]:
        if v is None or v == "":
            return None
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except Exception:
            return None


class OilPrice(MarketDataPoint):
    """Oil price data (Brent or WTI)."""
    benchmark: str  # "BRENT" or "WTI"
    price_per_barrel: Decimal = Field(alias="value")


class CryptoPrice(MarketDataPoint):
    """Cryptocurrency price data."""
    symbol: str  # "BTC", "ETH"
    price_usd: Decimal = Field(alias="value")
    price_cad: Optional[Decimal] = None


class BondYield(MarketDataPoint):
    """Government bond yield."""
    country: str  # "CA", "US"
    maturity_years: int  # 2, 5, 10
    yield_pct: Decimal = Field(alias="value")


class StockIndex(MarketDataPoint):
    """Stock market index value."""
    index_name: str  # "S&P 500", "TSX", etc.
    index_value: Decimal = Field(alias="value")


class ForexRate(MarketDataPoint):
    """Foreign exchange rate."""
    base_currency: str  # "USD"
    quote_currency: str  # "CAD"
    rate: Decimal = Field(alias="value")


class WeatherData(BaseModel):
    """Weather forecast and current conditions."""
    city: str
    country: str
    latitude: float
    longitude: float
    current_temp_c: Optional[Decimal] = None
    feels_like_c: Optional[Decimal] = None
    high_temp_c: Optional[Decimal] = None
    low_temp_c: Optional[Decimal] = None
    humidity_pct: Optional[int] = None
    wind_speed_kmh: Optional[Decimal] = None
    wind_direction: Optional[str] = None
    precipitation_probability_pct: Optional[int] = None
    precipitation_mm: Optional[Decimal] = None
    snow_probability_pct: Optional[int] = None
    weather_code: Optional[int] = None
    weather_description: Optional[str] = None
    alerts: List[str] = Field(default_factory=list)
    forecast_daily: List[dict] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: DataSource = DataSource.OPEN_METEO


class NewsItem(BaseModel):
    """News article/item."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    headline: str
    summary: str
    source: str
    url: str
    published_at: datetime
    category: str = "general"
    relevance_score: Optional[float] = None
    regions: List[str] = Field(default_factory=list)  # CA, US, MA, EU, etc.
    tags: List[str] = Field(default_factory=list)
    is_verified: bool = False
    language: str = "en"


class CalendarEvent(BaseModel):
    """Economic calendar event."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_name: str
    country: str
    date: date
    time: Optional[str] = None  # Local time as string
    timezone: str = "UTC"
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    importance: str = "medium"  # low, medium, high
    category: str = "economic"
    source: DataSource = DataSource.FINANCE_CALENDAR


class BriefingSection(BaseModel):
    """A section of the briefing."""
    title: str
    content: str
    order: int
    is_critical: bool = False
    metadata: dict = Field(default_factory=dict)


class MorningBriefing(BaseModel):
    """Complete morning briefing."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    briefing_date: date = Field(default_factory=date.today)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timezone: str = "America/Toronto"
    language: str = "en"
    mode: str = "full"
    status: BriefingStatus = BriefingStatus.PENDING

    # Sections
    executive_summary: Optional[str] = None
    weather: Optional[WeatherData] = None
    morocco_weather: Optional[WeatherData] = None
    markets: dict = Field(default_factory=dict)  # oil, crypto, bonds, indices, forex
    news: List[NewsItem] = Field(default_factory=list)
    essential_news: List[NewsItem] = Field(default_factory=list)
    mortgage_intelligence: Optional[str] = None
    savings_finance: Optional[str] = None
    economic_calendar: List[CalendarEvent] = Field(default_factory=list)
    priorities: List[str] = Field(default_factory=list)  # Exactly 3

    # Delivery tracking - stored as optional fields
    formatted_markdown: Optional[str] = None
    formatted_chunks: Optional[List[str]] = None
    delivery_attempts: List[Any] = Field(default_factory=list)
    error: Optional[str] = None

    @property
    def date(self) -> date:
        """Alias for briefing_date for backward compatibility with tests."""
        return self.briefing_date

    def get_markets_summary(self) -> str:
        """Generate a compact markets summary."""
        parts = []
        if "oil" in self.markets:
            oil = self.markets["oil"]
            if isinstance(oil, list):
                for o in oil:
                    if o.benchmark in ("BRENT", "WTI"):
                        parts.append(f"{o.benchmark}: ${o.price_per_barrel:.2f}/bbl")
        if "crypto" in self.markets:
            crypto = self.markets["crypto"]
            if isinstance(crypto, list):
                for c in crypto:
                    if c.symbol in ("BTC", "ETH"):
                        cad = f" (C${c.price_cad:,.0f})" if c.price_cad else ""
                        parts.append(f"{c.symbol}: ${c.price_usd:,.0f}{cad}")
        if "bonds" in self.markets:
            bonds = self.markets["bonds"]
            if isinstance(bonds, list):
                for b in bonds:
                    if b.country == "CA" and b.maturity_years in (2, 5, 10):
                        parts.append(f"CA {b.maturity_years}Y: {b.yield_pct:.2f}%")
        return " | ".join(parts)


class BriefingRecord(BaseModel):
    """Persisted briefing record."""
    id: UUID
    date: date
    briefing_json: str  # Serialized MorningBriefing
    status: BriefingStatus
    created_at: datetime
    updated_at: datetime
    delivery_status: str = "pending"  # pending, partial, delivered, failed


class UserSettings(BaseModel):
    """User preferences stored in database."""
    user_id: int
    timezone: str = "America/Toronto"
    briefing_hour: int = 7
    briefing_minute: int = 0
    schedule_weekdays_only: bool = False
    weather_city: str = "Montreal"
    weather_country: str = "Canada"
    weather_latitude: float = 45.5017
    weather_longitude: float = -73.5673
    morocco_weather_city: str = "Casablanca"
    morocco_weather_country: str = "Morocco"
    morocco_weather_latitude: float = 33.5731
    morocco_weather_longitude: float = -7.5898
    default_language: str = "en"
    enabled_languages: str = "en,fr,ar"
    briefing_mode: str = "full"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# For TYPE_CHECKING to resolve forward references
if TYPE_CHECKING:
    from src.models import DeliveryAttempt