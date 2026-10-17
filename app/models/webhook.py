"""SQLAlchemy 2.0 WebhookEndpoint and WebhookDelivery models."""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class WebhookEvent(enum.StrEnum):
    """Supported webhook event types."""

    APPLICATION_CREATED = "application.created"
    APPLICATION_STATUS_CHANGED = "application.status_changed"
    APPLICATION_WITHDRAWN = "application.withdrawn"
    APPLICATION_DELETED = "application.deleted"


class WebhookDeliveryStatus(enum.StrEnum):
    """Delivery attempt outcome."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEndpoint(Base, TimestampMixin):
    """Registered webhook endpoint owned by a user."""

    __tablename__ = "webhook_endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    events: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="*",
        doc="Comma-separated list of subscribed event types, or '*' for all events.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="webhook_endpoints")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="endpoint",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def subscribes_to(self, event: str) -> bool:
        """Return True if this endpoint is subscribed to the given event."""
        if self.events == "*":
            return True
        subscribed = {e.strip() for e in self.events.split(",")}
        return event in subscribed

    def __repr__(self) -> str:
        return f"<WebhookEndpoint(id={self.id}, user_id={self.user_id}, url='{self.url}')>"


class WebhookDelivery(Base, TimestampMixin):
    """Individual webhook dispatch attempt record."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    endpoint_id: Mapped[int] = mapped_column(
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        Enum(WebhookDeliveryStatus, native_enum=False, length=20),
        default=WebhookDeliveryStatus.PENDING,
        nullable=False,
        index=True,
    )
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    endpoint: Mapped["WebhookEndpoint"] = relationship("WebhookEndpoint", back_populates="deliveries")

    def mark_success(self, http_status: int, body: str) -> None:
        """Mark delivery as successful."""
        self.status = WebhookDeliveryStatus.SUCCESS
        self.http_status_code = http_status
        self.response_body = body[:2048]  # cap stored response
        self.delivered_at = datetime.now(UTC)
        self.attempt_count += 1

    def mark_failed(self, error: str, http_status: int | None = None, retry_at: datetime | None = None) -> None:
        """Mark delivery as failed, optionally scheduling a retry."""
        self.attempt_count += 1
        self.error_message = error[:2048]
        self.http_status_code = http_status
        if retry_at:
            self.status = WebhookDeliveryStatus.RETRYING
            self.next_retry_at = retry_at
        else:
            self.status = WebhookDeliveryStatus.FAILED

    def __repr__(self) -> str:
        return f"<WebhookDelivery(id={self.id}, event='{self.event}', status='{self.status}')>"
