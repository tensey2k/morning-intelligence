"""
Simple in-memory settings manager for Morning Intelligence Assistant.
Replaces the database repository with a simple in-memory storage.
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from src.config import settings


class InMemorySettingsManager:
    """Simple in-memory settings manager replacing the database repository."""

    def __init__(self):
        self._user_settings: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user settings by user ID."""
        async with self._lock:
            return self._user_settings.get(user_id)

    async def create_or_update_user_settings(self, user_id: int, **kwargs) -> Dict[str, Any]:
        """Create or update user settings."""
        async with self._lock:
            if user_id in self._user_settings:
                settings = self._user_settings[user_id]
                for key, value in kwargs.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                settings["updated_at"] = datetime.now()
            else:
                settings = {
                    "user_id": user_id,
                    "timezone": kwargs.get("timezone", "America/Toronto"),
                    "briefing_hour": kwargs.get("briefing_hour", 9),
                    "briefing_minute": kwargs.get("briefing_minute", 0),
                    "schedule_weekdays_only": kwargs.get("schedule_weekdays_only", False),
                    "weather_city": kwargs.get("weather_city", "Montreal"),
                    "weather_country": kwargs.get("weather_country", "Canada"),
                    "weather_latitude": kwargs.get("weather_latitude", 45.5017),
                    "weather_longitude": kwargs.get("weather_longitude", -73.5673),
                    "morocco_weather_city": kwargs.get("morocco_weather_city", "Casablanca"),
                    "morocco_weather_country": kwargs.get("morocco_weather_country", "Morocco"),
                    "morocco_weather_latitude": kwargs.get("morocco_weather_latitude", 33.5731),
                    "morocco_weather_longitude": kwargs.get("morocco_weather_longitude", -7.5898),
                    "default_language": kwargs.get("default_language", "en"),
                    "enabled_languages": kwargs.get("enabled_languages", "en,fr,ar"),
                    "briefing_mode": kwargs.get("briefing_mode", "full"),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
                self._user_settings[user_id] = settings
            return settings

    async def update_user_setting(self, user_id: int, key: str, value: Any) -> bool:
        """Update a single user setting."""
        async with self._lock:
            if user_id in self._user_settings:
                settings = self._user_settings[user_id]
                if hasattr(settings, key):
                    setattr(settings, key, value)
                else:
                    settings[key] = value
                settings["updated_at"] = datetime.now()
                return True
            else:
                # Create default settings if not exist
                await self.create_or_update_user_settings(user_id, **{key: value})
                return True

    async def save_briefing(self, briefing) -> None:
        """Save a briefing - in-memory version just logs it."""
        # In-memory version doesn't persist briefings
        pass

    async def get_latest_briefing(self) -> Optional[Dict]:
        """Get the most recent briefing record - not available in-memory."""
        return None

    async def get_latest_briefing_by_date(self, briefing_date) -> Optional[Dict]:
        """Get briefing for a specific date - not available in-memory."""
        return None

    async def record_delivery_attempt(
        self,
        briefing_id,
        channel: str,
        recipient_id: str,
        idempotency_key: str = None,
    ) -> Dict:
        """Record a delivery attempt - in-memory version just returns a mock object."""
        return {
            "id": str(uuid4()),
            "briefing_id": briefing_id,
            "channel": channel,
            "recipient_id": recipient_id,
            "status": "pending",
            "idempotency_key": idempotency_key or str(uuid4()),
        }

    async def update_delivery_attempt(
        self,
        attempt_id,
        status: str,
        message_id: str = None,
        provider_message_id: str = None,
        error: str = None,
    ) -> bool:
        """Update delivery attempt status - in-memory version just returns True."""
        return True

    async def check_idempotency(self, idempotency_key: str) -> bool:
        """Check if a delivery was already attempted - in-memory version always returns False."""
        return False

    async def create_run_status(
        self,
        run_type: str,
        data_sources_used: list = None,
    ) -> Dict:
        """Create a new run status record."""
        return {
            "id": str(uuid4()),
            "run_type": run_type,
            "status": "started",
            "data_sources_used": data_sources_used or [],
            "started_at": datetime.now(),
        }

    async def complete_run_status(
        self,
        run_id,
        status: str,
        briefing_id: str = None,
        errors: list = None,
        metadata: dict = None,
    ) -> bool:
        """Complete a run status record."""
        return True

    async def get_recent_runs(self, limit: int = 10) -> list:
        """Get recent run statuses."""
        return []


# Global instance
settings_manager = InMemorySettingsManager()