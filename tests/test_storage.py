"""
Tests for storage/repository layer (mocked).
"""
import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from src.storage.repository import Repository
from src.storage.models import UserSettingsModel, BriefingRecordModel, DeliveryAttemptModel, RunStatusModel
from src.models import MorningBriefing, BriefingStatus, DataSource, OilPrice, CryptoPrice, BondYield


class TestRepository:
    """Tests for Repository class."""

    @pytest.fixture
    def repo(self):
        """Create a repository for testing."""
        return Repository()

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_get_user_settings(self, repo, mock_session):
        """Test getting user settings."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = UserSettingsModel(
                user_id=12345,
                timezone="America/Toronto",
                briefing_hour=9,
            )
            mock_session.execute.return_value = mock_result

            settings = await repo.get_user_settings(12345)

            assert settings is not None
            assert settings.user_id == 12345
            assert settings.timezone == "America/Toronto"

    @pytest.mark.asyncio
    async def test_create_or_update_user_settings(self, repo, mock_session):
        """Test creating or updating user settings."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # No existing settings
            mock_session.execute.return_value = mock_result

            settings = await repo.create_or_update_user_settings(
                12345,
                timezone="America/Montreal",
                briefing_hour=8,
            )

            assert settings is not None
            assert settings.user_id == 12345
            assert settings.timezone == "America/Montreal"
            assert settings.briefing_hour == 8

    @pytest.mark.asyncio
    async def test_save_briefing(self, repo, mock_session):
        """Test saving a briefing."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # No existing briefing
            mock_session.execute.return_value = mock_result

            briefing = MorningBriefing(
                id=uuid4(),
                briefing_date=date.today(),
                timezone="America/Toronto",
                language="en",
                mode="full",
                status=BriefingStatus.GENERATED,
            )

            record = await repo.save_briefing(briefing)

            assert record is not None
            assert record.id == briefing.id
            assert record.date == briefing.briefing_date

    @pytest.mark.asyncio
    async def test_get_latest_briefing(self, repo, mock_session):
        """Test getting latest briefing."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_record = BriefingRecordModel(
                id=uuid4(),
                date=date.today(),
                briefing_json="{}",
                status="generated",
            )
            mock_result.scalar_one_or_none.return_value = mock_record
            mock_session.execute.return_value = mock_result

            briefing = await repo.get_latest_briefing()

            assert briefing is not None
            assert briefing.date == date.today()

    @pytest.mark.asyncio
    async def test_record_delivery_attempt(self, repo, mock_session):
        """Test recording delivery attempt."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            briefing_id = uuid4()
            attempt = await repo.record_delivery_attempt(
                briefing_id=briefing_id,
                channel="telegram",
                recipient_id="12345",
            )

            assert attempt is not None
            assert attempt.briefing_id == briefing_id
            assert attempt.channel == "telegram"
            assert attempt.recipient_id == "12345"

    @pytest.mark.asyncio
    async def test_check_idempotency(self, repo, mock_session):
        """Test idempotency check."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # Not found
            mock_session.execute.return_value = mock_result

            exists = await repo.check_idempotency("test-key-123")

            assert exists is False

    @pytest.mark.asyncio
    async def test_create_run_status(self, repo, mock_session):
        """Test creating run status."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            run = await repo.create_run_status(
                run_type="scheduled",
                data_sources_used=["Alpha Vantage", "FRED"],
            )

            assert run is not None
            assert run.run_type == "scheduled"
            assert run.status == "started"
            assert "Alpha Vantage" in run.data_sources_used

    @pytest.mark.asyncio
    async def test_complete_run_status(self, repo, mock_session):
        """Test completing run status."""
        with patch('src.storage.repository.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session

            run_id = uuid4()
            mock_result = MagicMock()
            mock_run = RunStatusModel(
                id=run_id,
                run_type="scheduled",
                status="started",
                started_at=datetime.now(timezone.utc),
            )
            mock_result.scalar_one_or_none.return_value = mock_run
            # Mock the update result to have rowcount > 0
            update_result = MagicMock()
            update_result.rowcount = 1
            mock_session.execute.return_value = update_result

            success = await repo.complete_run_status(
                run_id=run_id,
                status="completed",
                briefing_id=uuid4(),
                errors=[],
            )

            assert success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])