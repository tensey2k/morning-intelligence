"""
Configuration management for Morning Intelligence Assistant.
Uses Pydantic Settings for validation and type safety.
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Telegram
    # -------------------------------------------------------------------------
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token from @BotFather")
    telegram_allowed_user_id: int = Field(default=0, description="Your Telegram user ID (numeric)")

    # -------------------------------------------------------------------------
    # LLM Providers (Multiple with fallback)
    # -------------------------------------------------------------------------
    # Groq (PRIMARY)
    groq_api_key: str = Field(default="", description="Groq API key")
    groq_model: str = Field(default="llama-3.3-70b-versatile", description="Groq primary model")
    groq_fallback_model: str = Field(default="llama-3.1-8b-instant", description="Groq fallback model")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", description="Groq API base URL")

    # Google Gemini (FALLBACK)
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-1.5-flash", description="Gemini model")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta", description="Gemini API base URL")

    # OpenRouter (BACKUP)
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_model: str = Field(default="anthropic/claude-3.5-sonnet", description="OpenRouter model identifier")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", description="OpenRouter API base URL")
    openrouter_max_tokens: int = Field(default=8000, description="Max tokens per briefing generation")
    openrouter_temperature: float = Field(default=0.3, description="LLM temperature for synthesis")

    # Cloudflare Workers AI (BACKUP)
    cloudflare_account_id: str = Field(default="", description="Cloudflare account ID")
    cloudflare_api_token: str = Field(default="", description="Cloudflare API token")
    cloudflare_model: str = Field(default="@cf/meta/llama-3.1-8b-instruct", description="Cloudflare model")

    # LLM Selection
    llm_primary: str = Field(default="groq", description="Primary LLM provider: groq, gemini, openrouter, cloudflare")
    llm_fallback: str = Field(default="gemini", description="Fallback LLM provider")

    # -------------------------------------------------------------------------
    # Market Data APIs
    # -------------------------------------------------------------------------
    alpha_vantage_api_key: str = Field(default="", description="Alpha Vantage API key")
    alpha_vantage_base_url: str = Field(default="https://www.alphavantage.co/query", description="Alpha Vantage API base URL")

    fred_api_key: str = Field(default="", description="FRED API key")
    fred_base_url: str = Field(default="https://api.stlouisfed.org/fred", description="FRED API base URL")

    eia_api_key: str = Field(default="", description="EIA API key")
    eia_base_url: str = Field(default="https://api.eia.gov/v2", description="EIA API base URL")

    marketaux_api_key: str = Field(default="", description="MarketAux API key")
    marketaux_base_url: str = Field(default="https://api.marketaux.com/v1", description="MarketAux API base URL")

    bank_al_maghrib_api_key: str = Field(default="", description="Bank Al-Maghrib API key")
    bank_al_maghrib_base_url: str = Field(default="https://apihelpdesk.centralbankofmorocco.ma", description="Bank Al-Maghrib API base URL")

    # -------------------------------------------------------------------------
    # Scheduling & Timezone
    # -------------------------------------------------------------------------
    timezone: str = Field(default="America/Toronto", description="IANA timezone for scheduling")
    briefing_hour: int = Field(default=9, ge=0, le=23, description="Hour to send briefing (0-23)")
    briefing_minute: int = Field(default=0, ge=0, le=59, description="Minute to send briefing (0-59)")
    schedule_weekdays_only: bool = Field(default=False, description="Only send on weekdays (Mon-Fri)")

    # -------------------------------------------------------------------------
    # Location Settings
    # -------------------------------------------------------------------------
    weather_city: str = Field(default="Montreal", description="Primary weather city")
    weather_country: str = Field(default="Canada", description="Primary weather country")
    weather_latitude: float = Field(default=45.5017, description="Primary weather latitude")
    weather_longitude: float = Field(default=-73.5673, description="Primary weather longitude")

    morocco_weather_city: str = Field(default="Casablanca", description="Morocco weather city")
    morocco_weather_country: str = Field(default="Morocco", description="Morocco weather country")
    morocco_weather_latitude: float = Field(default=33.5731, description="Morocco weather latitude")
    morocco_weather_longitude: float = Field(default=-7.5898, description="Morocco weather longitude")

    # -------------------------------------------------------------------------
    # Language & Output
    # -------------------------------------------------------------------------
    default_language: str = Field(default="en", description="Default output language (en/fr/ar)")
    enabled_languages: str = Field(default="en,fr,ar", description="Comma-separated list of enabled languages")
    briefing_mode: str = Field(default="full", description="Briefing mode: compact, full, detailed")

    @field_validator("enabled_languages")
    @classmethod
    def parse_languages(cls, v: str) -> List[str]:
        return [lang.strip() for lang in v.split(",") if lang.strip()]

    @field_validator("briefing_mode")
    @classmethod
    def validate_briefing_mode(cls, v: str) -> str:
        valid_modes = {"compact", "full", "detailed"}
        if v not in valid_modes:
            raise ValueError(f"briefing_mode must be one of {valid_modes}")
        return v

    # -------------------------------------------------------------------------
    # Delivery Settings
    # -------------------------------------------------------------------------
    max_message_length: int = Field(default=4096, description="Max Telegram message length")
    split_long_messages: bool = Field(default=True, description="Split messages longer than max length")
    enable_markdown: bool = Field(default=True, description="Use Markdown formatting in Telegram")

    # -------------------------------------------------------------------------
    # Cost Controls
    # -------------------------------------------------------------------------
    max_llm_tokens_per_briefing: int = Field(default=8000, description="Max LLM tokens per briefing")
    max_api_calls_per_run: int = Field(default=50, description="Max external API calls per briefing run")

    # -------------------------------------------------------------------------
    # Derived Properties
    # -------------------------------------------------------------------------
    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return Path("./data")

    @property
    def languages(self) -> List[str]:
        """Get list of enabled languages."""
        return self.parse_languages(self.enabled_languages)

    @property
    def llm_config(self) -> dict:
        """Get LLM configuration for the primary provider."""
        configs = {
            "groq": {
                "api_key": self.groq_api_key,
                "model": self.groq_model,
                "fallback_model": self.groq_fallback_model,
                "base_url": self.groq_base_url,
            },
            "gemini": {
                "api_key": self.gemini_api_key,
                "model": self.gemini_model,
                "base_url": self.gemini_base_url,
            },
            "openrouter": {
                "api_key": self.openrouter_api_key,
                "model": self.openrouter_model,
                "base_url": self.openrouter_base_url,
                "max_tokens": self.openrouter_max_tokens,
                "temperature": self.openrouter_temperature,
            },
            "cloudflare": {
                "account_id": self.cloudflare_account_id,
                "api_token": self.cloudflare_api_token,
                "model": self.cloudflare_model,
            },
        }
        return configs.get(self.llm_primary, configs["groq"])


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export for easy importing
settings = get_settings()