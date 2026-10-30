"""
Repository layer for Morning Intelligence Assistant.
Provides high-level database operations.
"""
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.database import get_session
from src.storage.models import (
    UserSettingsModel,
    BriefingRecordModel,
    DeliveryAttemptModel,
    RunStatusModel,
)

logger = logging.getLogger(__name__)


class Repository:
    """High-level database operations."""

    # =========================================================================
    # USER SETTINGS
    # =========================================================================
    async def get_user_settings(self, user_id: int) -> Optional[UserSettingsModel]:
        """Get user settings by user ID."""
        async with get_session() as session:
            result = await session.execute(
                select(UserSettingsModel).where(UserSettingsModel.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def create_or_update_user_settings(self, user_id: int, **kwargs) -> UserSettingsModel:
        """Create or update user settings."""
        async with get_session() as session:
            settings = await self.get_user_settings(user_id)
            if settings:
                for key, value in kwargs.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                settings.updated_at = datetime.now(timezone.utc)
            else:
                settings = UserSettingsModel(user_id=user_id, **kwargs)
                session.add(settings)
            await session.commit()
            await session.refresh(settings)
            return settings

    async def update_user_setting(self, user_id: int, key: str, value: Any) -> bool:
        """Update a single user setting."""
        async with get_session() as session:
            result = await session.execute(
                update(UserSettingsModel)
                .where(UserSettingsModel.user_id == user_id)
                .values({key: value, "updated_at": datetime.now(timezone.utc)})
            )
            await session.commit()
            return result.rowcount > 0

    # =========================================================================
    # BRIEFING RECORDS
    # =========================================================================
    async def save_briefing(self, briefing) -> BriefingRecordModel:
        """Save a briefing to the database."""
        from src.models import MorningBriefing

        async with get_session() as session:
            # Check if briefing for this date already exists
            existing = await session.execute(
                select(BriefingRecordModel).where(BriefingRecordModel.date == briefing.date)
            )
            record = existing.scalar_one_or_none()

            briefing_json = briefing.model_dump_json()

            if record:
                record.briefing_json = briefing_json
                record.status = briefing.status.value if hasattr(briefing.status, 'value') else str(briefing.status)
                record.updated_at = datetime.now(timezone.utc)
            else:
                record = BriefingRecordModel(
                    id=briefing.id,
                    date=briefing.date,
                    briefing_json=briefing_json,
                    status=briefing.status.value if hasattr(briefing.status, 'value') else str(briefing.status),
                )
                session.add(record)

            await session.commit()
            await session.refresh(record)
            return record

    async def get_latest_briefing(self) -> Optional[BriefingRecordModel]:
        """Get the most recent briefing record."""
        async with get_session() as session:
            result = await session.execute(
                select(BriefingRecordModel)
                .order_by(BriefingRecordModel.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_briefing_by_date(self, briefing_date: date) -> Optional[BriefingRecordModel]:
        """Get briefing for a specific date."""
        async with get_session() as session:
            result = await session.execute(
                select(BriefingRecordModel).where(BriefingRecordModel.date == briefing_date)
            )
            return result.scalar_one_or_none()

    async def get_briefing_history(self, limit: int = 30) -> List[BriefingRecordModel]:
        """Get briefing history."""
        async with get_session() as session:
            result = await session.execute(
                select(BriefingRecordModel)
                .order_by(BriefingRecordModel.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    # =========================================================================
    # DELIVERY ATTEMPTS
    # =========================================================================
    async def record_delivery_attempt(
        self,
        briefing_id: UUID,
        channel: str,
        recipient_id: str,
        idempotency_key: str = None,
    ) -> DeliveryAttemptModel:
        """Record a delivery attempt."""
        async with get_session() as session:
            attempt = DeliveryAttemptModel(
                briefing_id=briefing_id,
                channel=channel,
                recipient_id=recipient_id,
                idempotency_key=idempotency_key or str(uuid4()),
            )
            session.add(attempt)
            await session.commit()
            await session.refresh(attempt)
            return attempt

    async def update_delivery_attempt(
        self,
        attempt_id: UUID,
        status: str,
        message_id: str = None,
        provider_message_id: str = None,
        error: str = None,
    ) -> bool:
        """Update delivery attempt status."""
        async with get_session() as session:
            values = {"status": status, "updated_at": datetime.now(timezone.utc)}
            if message_id:
                values["message_id"] = message_id
            if provider_message_id:
                values["provider_message_id"] = provider_message_id
            if error:
                values["error"] = error
            if status == "sent":
                values["sent_at"] = datetime.now(timezone.utc)
            elif status == "delivered":
                values["delivered_at"] = datetime.now(timezone.utc)

            result = await session.execute(
                update(DeliveryAttemptModel)
                .where(DeliveryAttemptModel.id == attempt_id)
                .values(values)
            )
            await session.commit()
            return result.rowcount > 0

    async def check_idempotency(self, idempotency_key: str) -> bool:
        """Check if a delivery was already attempted (idempotency)."""
        async with get_session() as session:
            result = await session.execute(
                select(DeliveryAttemptModel).where(DeliveryAttemptModel.idempotency_key == idempotency_key)
            )
            return result.scalar_one_or_none() is not None

    # =========================================================================
    # RUN STATUS
    # =========================================================================
    async def create_run_status(
        self,
        run_type: str,
        data_sources_used: List[str] = None,
    ) -> RunStatusModel:
        """Create a new run status record."""
        async with get_session() as session:
            run = RunStatusModel(
                run_type=run_type,
                status="started",
                data_sources_used=data_sources_used or [],
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def complete_run_status(
        self,
        run_id: UUID,
        status: str,
        briefing_id: UUID = None,
        errors: List[str] = None,
        metadata: Dict = None,
    ) -> bool:
        """Complete a run status record."""
        async with get_session() as session:
            # Get the run to calculate duration
            result = await session.execute(
                select(RunStatusModel).where(RunStatusModel.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                return False

            duration = (datetime.now(timezone.utc) - run.started_at).total_seconds()

            values = {
                "status": status,
                "completed_at": datetime.now(timezone.utc),
                "duration_seconds": duration,
                "errors": errors or [],
                "run_metadata": metadata or {},
            }
            if briefing_id:
                values["briefing_id"] = briefing_id

            result = await session.execute(
                update(RunStatusModel)
                .where(RunStatusModel.id == run_id)
                .values(values)
            )
            await session.commit()
            return result.rowcount > 0

    async def get_recent_runs(self, limit: int = 10) -> List[RunStatusModel]:
        """Get recent run statuses."""
        async with get_session() as session:
            result = await session.execute(
                select(RunStatusModel)
                .order_by(RunStatusModel.started_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    # =========================================================================
    # CLEANUP
    # =========================================================================
    async def cleanup_old_records(self, days: int = 90) -> int:
        """Clean up old briefing records and delivery attempts."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        async with get_session() as session:
            # Delete old delivery attempts
            result = await session.execute(
                delete(DeliveryAttemptModel).where(DeliveryAttemptModel.created_at < cutoff)
            )
            attempts_deleted = result.rowcount

            # Delete old briefing records (cascades to delivery attempts)
            result = await session.execute(
                delete(BriefingRecordModel).where(BriefingRecordModel.created_at < cutoff)
            )
            briefings_deleted = result.rowcount

            # Delete old run statuses
            result = await session.execute(
                delete(RunStatusModel).where(RunStatusModel.started_at < cutoff)
            )
            runs_deleted = result.rowcount

            await session.commit()
            logger.info(f"Cleaned up: {briefings_deleted} briefings, {attempts_deleted} attempts, {runs_deleted} runs")
            return briefings_deleted + attempts_deleted + runs_deleted


# Global instance
repository = Repository()