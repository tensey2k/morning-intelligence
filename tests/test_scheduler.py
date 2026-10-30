"""
Tests for scheduler functionality.
"""
import pytest
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

from src.scheduler.manager import SchedulerManager


class TestSchedulerManager:
    """Tests for SchedulerManager."""

    @pytest.fixture
    def scheduler_manager(self):
        """Create a scheduler manager for testing."""
        manager = SchedulerManager()
        # Don't actually initialize the scheduler
        manager._initialized = True
        manager.scheduler = MagicMock()
        manager.scheduler.running = True
        manager.scheduler.get_job = MagicMock()
        manager.scheduler.add_job = MagicMock()
        manager.scheduler.remove_job = MagicMock()
        manager.scheduler.get_jobs = MagicMock(return_value=[])
        return manager

    def test_timezone_setup(self, scheduler_manager):
        """Test timezone is set correctly."""
        assert str(scheduler_manager.timezone) == "America/Toronto"

    @pytest.mark.asyncio
    async def test_schedule_daily_briefing(self, scheduler_manager):
        """Test scheduling daily briefing."""
        await scheduler_manager.schedule_daily_briefing(hour=9, minute=0, weekdays_only=False)

        # Verify add_job was called
        scheduler_manager.scheduler.add_job.assert_called_once()
        call_args = scheduler_manager.scheduler.add_job.call_args
        assert call_args[1]['id'] == "daily_briefing"
        assert call_args[1]['name'] == "Daily Morning Briefing"

    @pytest.mark.asyncio
    async def test_schedule_weekdays_only(self, scheduler_manager):
        """Test scheduling weekdays only."""
        await scheduler_manager.schedule_daily_briefing(hour=9, minute=0, weekdays_only=True)

        call_args = scheduler_manager.scheduler.add_job.call_args
        trigger = call_args[1]['trigger']
        # Check that day_of_week is set to weekdays (0-4) - Monday=0, Friday=4
        # day_of_week field is at index 4, with expressions containing RangeExpression
        day_of_week_field = trigger.fields[4]  # day_of_week is the 5th field (index 4)
        assert hasattr(day_of_week_field, 'expressions')
        range_expr = day_of_week_field.expressions[0]
        assert range_expr.first == 0  # Monday
        assert range_expr.last == 4   # Friday

    def test_get_status(self, scheduler_manager):
        """Test getting scheduler status."""
        mock_job = MagicMock()
        mock_job.id = "daily_briefing"
        mock_job.next_run_time = datetime(2024, 1, 16, 9, 0)
        scheduler_manager.scheduler.get_jobs.return_value = [mock_job]

        status = scheduler_manager.get_status()

        assert status['running'] is True
        assert status['timezone'] == "America/Toronto"
        assert status['jobs_count'] == 1
        assert status['next_run'] is not None

    @pytest.mark.asyncio
    async def test_get_next_run(self, scheduler_manager):
        """Test getting next run time."""
        mock_job = MagicMock()
        mock_job.next_run_time = datetime(2024, 1, 16, 9, 0)
        scheduler_manager.scheduler.get_job.return_value = mock_job

        next_run = await scheduler_manager.get_next_run()

        assert next_run == datetime(2024, 1, 16, 9, 0)

    @pytest.mark.asyncio
    async def test_get_next_run_no_job(self, scheduler_manager):
        """Test getting next run when no job scheduled."""
        scheduler_manager.scheduler.get_job.return_value = None

        next_run = await scheduler_manager.get_next_run()

        assert next_run is None

    @pytest.mark.asyncio
    async def test_shutdown(self, scheduler_manager):
        """Test scheduler shutdown."""
        await scheduler_manager.shutdown()
        scheduler_manager.scheduler.shutdown.assert_called_once_with(wait=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])