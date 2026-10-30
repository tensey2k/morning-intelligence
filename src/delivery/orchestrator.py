"""
Delivery Orchestrator for Morning Intelligence Assistant.
Handles: Telegram delivery, retries, idempotency, duplicate prevention.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.config import settings
from src.channels.telegram import telegram_channel
from src.settings_manager import settings_manager
from src.models import (
    BriefingStatus,
    DeliveryAttempt,
    DeliveryChannel,
    DeliveryStatus,
    MorningBriefing,
)

logger = logging.getLogger(__name__)


class DeliveryOrchestrator:
    """Orchestrates briefing delivery with fallback, retries, and deduplication."""

    def __init__(self):
        self.max_retries = 3
        self.base_retry_delay = 5  # seconds
        self.max_retry_delay = 60  # seconds
        self.whatsapp_timeout = 30  # seconds

    async def deliver_briefing(self, briefing: MorningBriefing) -> List[DeliveryAttempt]:
        """
        Deliver briefing with fallback logic:
        1. Try Telegram first
        2. On definitive failure -> log error
        3. On timeout/ambiguous -> wait, then retry
        4. Prevent duplicates using idempotency keys
        4. Record all attempts
        """
        all_attempts = []

        # Since WhatsApp is abandoned, deliver directly via Telegram
        logger.info(f"Delivering briefing {briefing.id} via Telegram")

        telegram_attempts = await self._deliver_via_telegram(briefing)
        all_attempts.extend(telegram_attempts)

        # Update briefing delivery status
        await self._update_briefing_delivery_status(briefing, all_attempts)

        return all_attempts

    async def _deliver_via_telegram(self, briefing: MorningBriefing) -> List[DeliveryAttempt]:
        """Deliver briefing via Telegram with retries."""
        attempts = []

        for chunk_index, chunk in enumerate(briefing.formatted_chunks):
            idempotency_key = f"telegram_{briefing.id}_{chunk_index}_{briefing.date.isoformat()}"

            # Check idempotency
            existing = await settings_manager.check_idempotency(idempotency_key)
            if existing:
                logger.info(f"Skipping duplicate delivery: {idempotency_key}")
                attempts.append(DeliveryAttempt(
                    briefing_id=briefing.id,
                    channel=DeliveryChannel.TELEGRAM,
                    recipient_id=str(settings.telegram_allowed_user_id),
                    status=DeliveryStatus.DELIVERED,
                    idempotency_key=idempotency_key,
                ))
                continue

            attempt = DeliveryAttempt(
                briefing_id=briefing.id,
                channel=DeliveryChannel.TELEGRAM,
                recipient_id=str(settings.telegram_allowed_user_id),
                status=DeliveryStatus.PENDING,
                idempotency_key=idempotency_key,
            )

            # Retry logic with exponential backoff
            for retry in range(self.max_retries):
                try:
                    attempt.status = DeliveryStatus.SENT
                    attempt.attempts = retry + 1
                    attempt.sent_at = datetime.now(timezone.utc)

                    message = await telegram_channel.application.bot.send_message(
                        chat_id=settings.telegram_allowed_user_id,
                        text=chunk,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                    )

                    attempt.status = DeliveryStatus.SENT
                    attempt.provider_message_id = str(message.message_id)
                    attempt.updated_at = datetime.now(timezone.utc)

                    # Save successful attempt
                    await settings_manager.save_delivery_attempt(attempt)

                    # For Telegram, sent = delivered (no webhook needed for basic delivery)
                    attempt.status = DeliveryStatus.DELIVERED
                    attempt.delivered_at = datetime.now(timezone.utc)
                    attempt.updated_at = datetime.now(timezone.utc)
                    await settings_manager.update_delivery_attempt(attempt.id, status=DeliveryStatus.DELIVERED, delivered_at=attempt.delivered_at)

                    attempts.append(attempt)
                    logger.info(f"Telegram delivery successful for briefing {briefing.id}, chunk {chunk_index}")
                    break

                except Exception as e:
                    attempt.error = str(e)
                    attempt.status = DeliveryStatus.FAILED if retry == self.max_retries - 1 else DeliveryStatus.RETRYING
                    attempt.updated_at = datetime.now(timezone.utc)
                    await settings_manager.save_delivery_attempt(attempt)

                    if retry < self.max_retries - 1:
                        delay = min(self.base_retry_delay * (2 ** retry), self.max_retry_delay)
                        logger.warning(f"Telegram delivery failed (attempt {retry + 1}), retrying in {delay}s: {e}")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Telegram delivery failed after {self.max_retries} attempts: {e}")
                        attempts.append(attempt)

        return attempts

    async def _update_briefing_delivery_status(self, briefing: MorningBriefing, attempts: List[DeliveryAttempt]):
        """Update briefing record with overall delivery status."""
        if not attempts:
            await settings_manager.update_briefing_status(briefing.id, BriefingStatus.FAILED)
            return

        statuses = [a.status for a in attempts]
        if all(s == DeliveryStatus.DELIVERED for s in statuses):
            delivery_status = "delivered"
        elif any(s == DeliveryStatus.DELIVERED for s in statuses):
            delivery_status = "partial"
        else:
            delivery_status = "failed"

        await settings_manager.update_briefing_delivery_status(briefing.id, delivery_status)

        # Update briefing status
        if delivery_status == "delivered":
            await settings_manager.update_briefing_status(briefing.id, BriefingStatus.DELIVERED)
        elif delivery_status == "partial":
            await settings_manager.update_briefing_status(briefing.id, BriefingStatus.PARTIAL)
        else:
            await settings_manager.update_briefing_status(briefing.id, BriefingStatus.FAILED)

    def _model_to_attempt(self, model) -> DeliveryAttempt:
        """Convert SQLAlchemy model to DeliveryAttempt."""
        return DeliveryAttempt(
            id=model.id,
            briefing_id=model.briefing_id,
            channel=DeliveryChannel(model.channel),
            recipient_id=model.recipient_id,
            status=DeliveryStatus(model.status),
            message_id=model.message_id,
            provider_message_id=model.provider_message_id,
            error=model.error,
            attempts=model.attempts,
            sent_at=model.sent_at,
            delivered_at=model.delivered_at,
            idempotency_key=model.idempotency_key,
        )

    async def retry_failed_deliveries(self, briefing_id: str) -> List[DeliveryAttempt]:
        """Retry failed delivery attempts for a briefing."""
        from uuid import UUID
        briefing_uuid = UUID(briefing_id)

        attempts = await settings_manager.get_delivery_attempts(briefing_uuid)
        failed_attempts = [a for a in attempts if a.status == DeliveryStatus.FAILED]

        if not failed_attempts:
            logger.info(f"No failed deliveries to retry for briefing {briefing_id}")
            return []

        # Get briefing
        briefing_record = await settings_manager.get_briefing(briefing_uuid)
        if not briefing_record:
            logger.error(f"Briefing {briefing_id} not found")
            return []

        # Reconstruct briefing object
        briefing = MorningBriefing.model_validate_json(briefing_record.briefing_json)

        # Retry only failed chunks
        retry_attempts = []
        for failed in failed_attempts:
            chunk_index = int(failed.idempotency_key.split("_")[-2]) if "_" in failed.idempotency_key else 0
            if chunk_index < len(briefing.formatted_chunks):
                chunk = briefing.formatted_chunks[chunk_index]

                # Create new idempotency key for retry
                new_key = f"{failed.idempotency_key}_retry_{datetime.now(timezone.utc).timestamp()}"

                attempt = DeliveryAttempt(
                    briefing_id=briefing.id,
                    channel=DeliveryChannel(failed.channel),
                    recipient_id=failed.recipient_id,
                    status=DeliveryStatus.PENDING,
                    idempotency_key=new_key,
                )

                try:
                    if failed.channel == DeliveryChannel.TELEGRAM:
                        message = await telegram_channel.application.bot.send_message(
                            chat_id=settings.telegram_allowed_user_id,
                            text=chunk,
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                        )
                        attempt.status = DeliveryStatus.DELIVERED
                        attempt.provider_message_id = str(message.message_id)
                        attempt.sent_at = datetime.now(timezone.utc)
                        attempt.delivered_at = datetime.now(timezone.utc)
                    else:
                        attempt.status = DeliveryStatus.FAILED
                        attempt.error = "Channel not supported"

                    attempt.updated_at = datetime.now(timezone.utc)
                    await settings_manager.save_delivery_attempt(attempt)
                    retry_attempts.append(attempt)

                except Exception as e:
                    attempt.status = DeliveryStatus.FAILED
                    attempt.error = str(e)
                    attempt.updated_at = datetime.now(timezone.utc)
                    await settings_manager.save_delivery_attempt(attempt)
                    retry_attempts.append(attempt)

        # Update overall status
        await self._update_briefing_delivery_status(briefing, retry_attempts)

        return retry_attempts

    async def get_delivery_status(self, briefing_id: str) -> Dict[str, Any]:
        """Get comprehensive delivery status for a briefing."""
        from uuid import UUID
        briefing_uuid = UUID(briefing_id)

        briefing_record = await settings_manager.get_briefing(briefing_uuid)
        if not briefing_record:
            return {"error": "Briefing not found"}

        attempts = await settings_manager.get_delivery_attempts(briefing_uuid)

        return {
            "briefing_id": str(briefing_id),
            "date": briefing_record.date.isoformat(),
            "generation_status": briefing_record.status,
            "delivery_status": briefing_record.delivery_status,
            "attempts": [
                {
                    "channel": a.channel,
                    "status": a.status,
                    "attempts": a.attempts,
                    "sent_at": a.sent_at.isoformat() if a.sent_at else None,
                    "delivered_at": a.delivered_at.isoformat() if a.delivered_at else None,
                    "error": a.error,
                    "provider_message_id": a.provider_message_id,
                }
                for a in attempts
            ],
        }


# Global instance
delivery_orchestrator = DeliveryOrchestrator()