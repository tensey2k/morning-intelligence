"""
Scheduler Manager for Morning Intelligence Assistant.
Uses APScheduler with timezone-aware daily scheduling and in-memory job store.
"""
import asyncio
import logging
from datetime import datetime, time
from typing import Any, Dict, Optional

import pytz
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.briefing.engine import briefing_engine
from src.settings_manager import settings_manager

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages scheduled jobs for daily briefing delivery."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.timezone = pytz.timezone(settings.timezone)
        self._initialized = False

    async def initialize(self):
        """Initialize the scheduler with job store."""
        if self._initialized:
            return

        # Create job store (in-memory for simplicity)
        jobstores = {
            "default": MemoryJobStore()
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=self.timezone,
            job_defaults={
                "coalesce": True,  # Combine missed runs
                "max_instances": 1,  # Prevent duplicate runs
                "misfire_grace_time": 300,  # 5 minutes grace period
            },
        )

        self.scheduler.start()
        self._initialized = True
        logger.info("Scheduler initialized")

        # Schedule the daily briefing job
        await self.schedule_daily_briefing()

    async def schedule_daily_briefing(
        self,
        hour: int = None,
        minute: int = None,
        weekdays_only: bool = None,
    ):
        """Schedule the daily briefing job."""
        if not self.scheduler:
            await self.initialize()

        hour = hour if hour is not None else settings.briefing_hour
        minute = minute if minute is not None else settings.briefing_minute
        weekdays_only = weekdays_only if weekdays_only is not None else settings.schedule_weekdays_only

        # Remove existing job if any
        self.scheduler.remove_job("daily_briefing", jobstore="default")

        # Create cron trigger
        if weekdays_only:
            # Monday-Friday (0-4 in cron)
            day_of_week = "0-4"
        else:
            day_of_week = "*"

        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=day_of_week,
            timezone=self.timezone,
        )

        # Add job
        self.scheduler.add_job(
            self._run_daily_briefing,
            trigger=trigger,
            id="daily_briefing",
            name="Daily Morning Briefing",
            jobstore="default",
            replace_existing=True,
        )

        logger.info(f"Daily briefing scheduled for {hour:02d}:{minute:02d} {self.timezone} ({'weekdays' if weekdays_only else 'daily'})")

    async def reschedule_daily_briefing(
        self,
        hour: int = None,
        minute: int = None,
    ):
        """Reschedule the daily briefing (called when settings change)."""
        await self.schedule_daily_briefing(hour, minute)

    def _get_telegram_bot(self):
        """Lazy import to avoid circular imports."""
        from src.telegram.bot import telegram_bot
        return telegram_bot

    async def _run_daily_briefing(self):
        """Run the daily briefing generation and delivery."""
        logger.info("Starting scheduled daily briefing")

        try:
            # Generate briefing
            briefing = await briefing_engine.generate_briefing()

            if briefing.status.value == "failed":
                logger.error(f"Briefing generation failed: {briefing.error}")
                # Send error notification
                telegram_bot = self._get_telegram_bot()
                await telegram_bot.send_message(
                    f"❌ **Daily Briefing Failed**\n\n"
                    f"Generation failed: {briefing.error[:200]}\n\n"
                    f"Check `/status` for details."
                )
                return

            # Send briefing
            telegram_bot = self._get_telegram_bot()
            success = await telegram_bot.send_briefing(briefing)

            if success:
                logger.info("Daily briefing delivered successfully")
                await settings_manager.save_briefing(briefing)
            else:
                logger.error("Failed to deliver daily briefing")
                telegram_bot = self._get_telegram_bot()
                await telegram_bot.send_message(
                    "❌ **Daily Briefing Delivery Failed**\n\n"
                    "The briefing was generated but could not be delivered. "
                    "Check Telegram connection."
                )

        except Exception as e:
            logger.error(f"Daily briefing job failed: {e}")
            try:
                telegram_bot = self._get_telegram_bot()
                await telegram_bot.send_message(
                    f"❌ **Daily Briefing Job Failed**\n\n"
                    f"Error: {str(e)[:200]}\n\n"
                    f"Check logs for details."
                )
            except Exception:
                pass

    async def get_next_run(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        if not self.scheduler:
            return None

        job = self.scheduler.get_job("daily_briefing", jobstore="default")
        if job and job.next_run_time:
            return job.next_run_time
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        if not self.scheduler:
            return {"running": False, "timezone": str(self.timezone)}

        jobs = self.scheduler.get_jobs()
        next_run = None
        for job in jobs:
            if job.id == "daily_briefing":
                next_run = job.next_run_time
                break

        return {
            "running": self.scheduler.running,
            "timezone": str(self.timezone),
            "jobs_count": len(jobs),
            "next_run": next_run.isoformat() if next_run else None,
            "uptime": "Running" if self.scheduler.running else "Stopped",
        }

    async def run_briefing_now(self, mode: str = "full") -> bool:
        """Manually trigger a briefing generation and delivery."""
        logger.info("Manual briefing trigger")

        try:
            briefing = await briefing_engine.generate_briefing(mode=mode)

            if briefing.status.value == "failed":
                return False

            telegram_bot = self._get_telegram_bot()
            success = await telegram_bot.send_briefing(briefing)
            if success:
                await settings_manager.save_briefing(briefing)
            return success

        except Exception as e:
            logger.error(f"Manual briefing failed: {e}")
            return False

    async def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler shut down")


# Global instance
scheduler_manager = SchedulerManager()