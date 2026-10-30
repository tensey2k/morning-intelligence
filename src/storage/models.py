"""
SQLAlchemy models for Morning Intelligence Assistant.
"""
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.storage.database import Base


class UserSettingsModel(Base):
    """User settings stored in database."""
    __tablename__ = "user_settings"
    __table_args__ = {"extend_existing": True}

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Toronto")
    briefing_hour: Mapped[int] = mapped_column(Integer, default=9)
    briefing_minute: Mapped[int] = mapped_column(Integer, default=0)
    schedule_weekdays_only: Mapped[bool] = mapped_column(Boolean, default=False)
    weather_city: Mapped[str] = mapped_column(String(100), default="Montreal")
    weather_country: Mapped[str] = mapped_column(String(100), default="Canada")
    weather_latitude: Mapped[float] = mapped_column(default=45.5017)
    weather_longitude: Mapped[float] = mapped_column(default=-73.5673)
    morocco_weather_city: Mapped[str] = mapped_column(String(100), default="Casablanca")
    morocco_weather_country: Mapped[str] = mapped_column(String(100), default="Morocco")
    morocco_weather_latitude: Mapped[float] = mapped_column(default=33.5731)
    morocco_weather_longitude: Mapped[float] = mapped_column(default=-7.5898)
    default_language: Mapped[str] = mapped_column(String(10), default="en")
    enabled_languages: Mapped[str] = mapped_column(String(50), default="en,fr,ar")
    briefing_mode: Mapped[str] = mapped_column(String(20), default="full")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BriefingRecordModel(Base):
    """Persisted briefing records."""
    __tablename__ = "briefing_records"
    __table_args__ = (
        Index("ix_briefing_records_date_status", "date", "status"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    date: Mapped[date] = mapped_column(Date, index=True)
    briefing_json: Mapped[str] = mapped_column(Text)  # Serialized MorningBriefing
    status: Mapped[str] = mapped_column(String(20), default="pending")
    delivery_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to delivery attempts
    delivery_attempts: Mapped[List["DeliveryAttemptModel"]] = relationship(
        "DeliveryAttemptModel",
        back_populates="briefing",
        cascade="all, delete-orphan",
    )


class DeliveryAttemptModel(Base):
    """Record of delivery attempts."""
    __tablename__ = "delivery_attempts"
    __table_args__ = (
        Index("ix_delivery_attempts_briefing_status", "briefing_id", "status"),
        UniqueConstraint("idempotency_key", name="uq_delivery_idempotency"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    briefing_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("briefing_records.id", ondelete="CASCADE"),
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(20), default="telegram")
    recipient_id: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    message_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, default=lambda: str(uuid4()))

    # Relationship to briefing
    briefing: Mapped["BriefingRecordModel"] = relationship("BriefingRecordModel", back_populates="delivery_attempts")


class RunStatusModel(Base):
    """Track scheduler run status for monitoring."""
    __tablename__ = "run_status"
    __table_args__ = (
        Index("ix_run_status_started_at", "started_at"),
        Index("ix_run_status_status", "status"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_type: Mapped[str] = mapped_column(String(50))  # scheduled, manual, retry
    status: Mapped[str] = mapped_column(String(20))  # started, completed, failed, partial
    briefing_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    data_sources_used: Mapped[List[str]] = mapped_column(JSON, default=list)
    errors: Mapped[List[str]] = mapped_column(JSON, default=list)
    run_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # Renamed from metadata