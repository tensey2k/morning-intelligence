"""
Open-Meteo API source for weather data.
Free non-commercial tier, no API key required.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import DataSource, WeatherData


class OpenMeteoSource(DataSourceBase):
    """Open-Meteo weather API client."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    # WMO Weather interpretation codes
    WEATHER_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }

    def __init__(self):
        super().__init__(
            name="Open-Meteo",
            base_url=self.BASE_URL,
            api_key=None,
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
            params = {
                "latitude": 45.5017,
                "longitude": -73.5673,
                "current_weather": "true",
            }
            await self._request("GET", "", params=params)
            return True
        except Exception:
            return False

    def _get_weather_description(self, code: int) -> str:
        """Get human-readable weather description from WMO code."""
        return self.WEATHER_CODES.get(code, f"Unknown (code {code})")

    def _parse_alerts(self, data: Dict[str, Any]) -> List[str]:
        """Parse weather alerts from response."""
        alerts = []
        if "alerts" in data:
            for alert in data["alerts"]:
                alerts.append(f"{alert.get('event', 'Weather Alert')}: {alert.get('description', '')}")
        return alerts

    async def get_weather(
        self,
        latitude: float = None,
        longitude: float = None,
        city: str = None,
        country: str = None,
        forecast_days: int = 3,
    ) -> WeatherData:
        """Get current weather and forecast for a location."""
        if latitude is None:
            latitude = settings.weather_latitude
        if longitude is None:
            longitude = settings.weather_longitude
        if city is None:
            city = settings.weather_city
        if country is None:
            country = settings.weather_country

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,snowfall_sum,wind_speed_10m_max,weather_code",
            "timezone": settings.timezone,
            "forecast_days": forecast_days,
        }

        try:
            data = await self._request("GET", "", params=params)

            # Current weather
            current = data.get("current_weather", {})
            current_temp = current.get("temperature")
            wind_speed = current.get("windspeed")
            wind_direction = current.get("winddirection")
            weather_code = current.get("weathercode")

            # Daily forecast
            daily = data.get("daily", {})
            today_idx = 0

            high_temp = None
            low_temp = None
            precip_prob = None
            precip_mm = None
            snow_prob = None

            if "temperature_2m_max" in daily and daily["temperature_2m_max"]:
                high_temp = daily["temperature_2m_max"][today_idx]
            if "temperature_2m_min" in daily and daily["temperature_2m_min"]:
                low_temp = daily["temperature_2m_min"][today_idx]
            if "precipitation_probability_max" in daily and daily["precipitation_probability_max"]:
                precip_prob = daily["precipitation_probability_max"][today_idx]
            if "precipitation_sum" in daily and daily["precipitation_sum"]:
                precip_mm = daily["precipitation_sum"][today_idx]
            if "snowfall_sum" in daily and daily["snowfall_sum"]:
                snow_prob = min(100, int(daily["snowfall_sum"][today_idx] * 10))  # Rough estimate

            # Build forecast daily list
            forecast_daily = []
            for i in range(min(forecast_days, len(daily.get("time", [])))):
                forecast_daily.append({
                    "date": daily["time"][i],
                    "high_temp_c": daily["temperature_2m_max"][i] if "temperature_2m_max" in daily else None,
                    "low_temp_c": daily["temperature_2m_min"][i] if "temperature_2m_min" in daily else None,
                    "precip_probability_pct": daily["precipitation_probability_max"][i] if "precipitation_probability_max" in daily else None,
                    "precip_mm": daily["precipitation_sum"][i] if "precipitation_sum" in daily else None,
                    "weather_code": daily["weather_code"][i] if "weather_code" in daily else None,
                    "weather_description": self._get_weather_description(daily["weather_code"][i]) if "weather_code" in daily else None,
                })

            # Parse alerts
            alerts = self._parse_alerts(data)

            return WeatherData(
                city=city,
                country=country,
                latitude=latitude,
                longitude=longitude,
                current_temp_c=Decimal(str(current_temp)) if current_temp is not None else None,
                feels_like_c=None,  # Open-Meteo doesn't provide feels-like directly
                high_temp_c=Decimal(str(high_temp)) if high_temp is not None else None,
                low_temp_c=Decimal(str(low_temp)) if low_temp is not None else None,
                humidity_pct=None,  # Would need hourly data at current hour
                wind_speed_kmh=Decimal(str(wind_speed)) if wind_speed is not None else None,
                wind_direction=self._degrees_to_direction(wind_direction) if wind_direction is not None else None,
                precipitation_probability_pct=precip_prob,
                precipitation_mm=Decimal(str(precip_mm)) if precip_mm is not None else None,
                snow_probability_pct=snow_prob,
                weather_code=weather_code,
                weather_description=self._get_weather_description(weather_code) if weather_code is not None else None,
                alerts=alerts,
                forecast_daily=forecast_daily,
                timestamp=datetime.now(timezone.utc),
                source=DataSource.OPEN_METEO,
            )

        except Exception as e:
            raise DataSourceError(f"Failed to fetch weather: {e}", self.name)

    def _degrees_to_direction(self, degrees: float) -> str:
        """Convert wind direction degrees to cardinal direction."""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / 22.5) % 16
        return directions[index]

    async def get_montreal_weather(self) -> WeatherData:
        """Get weather for Montreal (default)."""
        return await self.get_weather(
            latitude=settings.weather_latitude,
            longitude=settings.weather_longitude,
            city=settings.weather_city,
            country=settings.weather_country,
        )

    async def get_morocco_weather(self) -> WeatherData:
        """Get weather for Casablanca, Morocco."""
        return await self.get_weather(
            latitude=settings.morocco_weather_latitude,
            longitude=settings.morocco_weather_longitude,
            city=settings.morocco_weather_city,
            country=settings.morocco_weather_country,
        )