"""
Scheduler for Morning Intelligence Assistant.
Uses APScheduler for timezone-aware, persistent scheduling.
"""
import logging
from datetime import date, datetime, time
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.asyncio import AsyncIOExecutor

from src.config import settings
from src.storage.database import db

logger = logging.getLogger(__name__)


class BriefingScheduler:
    """Manages scheduled briefing generation and delivery."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._job_id = "daily_morning_briefing"

    async def initialize(self):
        """Initialize the scheduler with persistent job store."""
        # Configure job store (SQLite for dev, PostgreSQL for prod)
        jobstore_url = settings.database_url
        if jobstore_url.startswith("sqlite://"):
            jobstore_url = jobstore_url.replace("sqlite://", "sqlite://")

        jobstores = {
            "default": SQLAlchemyJobStore(url=jobstore_url),
        }

        executors = {
            "default": AsyncIOExecutor(),
        }

        job_defaults = {
            "coalesce": True,  # Combine missed runs
            "max_instances": 1,  # Prevent overlapping runs
            "misfire_grace_time": 300,  # 5 minutes grace period
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=settings.timezone,
        )

        self.scheduler.start()
        logger.info(f"Scheduler started with timezone {settings.timezone}")

    async def schedule_daily_briefing(self, hour: int = None, minute: int = None, weekdays_only: bool = None):
        """Schedule the daily morning briefing job."""
        if hour is None:
            hour = settings.briefing_hour
        if minute is None:
            minute = settings.briefing_minute
        if weekdays_only is None:
            weekdays_only = settings.schedule_weekdays_only

        # Remove existing job if present
        if self.scheduler.get_job(self._job_id):
            self.scheduler.remove_job(self._job_id)

        # Build cron expression
        if weekdays_only:
            day_of_week = "mon-fri"
        else:
            day_of_week = "*"

        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=day_of_week,
            timezone=settings.timezone,
        )

        self.scheduler.add_job(
            func=self._run_briefing_job,
            trigger=trigger,
            id=self._job_id,
            name="Daily Morning Briefing",
            replace_existing=True,
        )

        logger.info(
            f"Scheduled daily briefing at {hour:02d}:{minute:02d} "
            f"({'weekdays only' if weekdays_only else 'every day'}) in {settings.timezone}"
        )

    async def _run_briefing_job(self):
        """Job function to generate and deliver briefing."""
        from src.briefing.engine import briefing_engine
        from src.channels.telegram import telegram_channel
        from src.delivery.orchestrator import delivery_orchestrator

        logger.info("Starting scheduled briefing generation...")

        try:
            # Generate briefing
            briefing = await briefing_engine.generate_full_briefing()

            if briefing.status != briefing.status.__class__.GENERATED:
                logger.error(f"Briefing generation failed: {briefing.error}")
                return

            # Deliver via orchestrator (handles fallback, retries, etc.)
            await delivery_orchestrator.deliver_briefing(briefing)

            logger.info(f"Scheduled briefing completed for {briefing.date}")

        except Exception as e:
            logger.error(f"Scheduled briefing job failed: {e}")

    async def run_briefing_now(self) -> bool:
        """Manually trigger a briefing generation and delivery."""
        logger.info("Manual briefing trigger requested")
        await self._run_briefing_job()
        return True

    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        job = self.scheduler.get_job(self._job_id)
        if job:
            return job.next_run_time
        return None

    def get_job_info(self) -> dict:
        """Get information about the scheduled job."""
        job = self.scheduler.get_job(self._job_id)
        if not job:
            return {"scheduled": False}

        return {
            "scheduled": True,
            "job_id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }

    async def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler shutdown")


# Global instance
briefing_scheduler = BriefingScheduler()