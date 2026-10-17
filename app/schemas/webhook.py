"""Pydantic schemas for webhook endpoint management and delivery logs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.webhook import WebhookDeliveryStatus, WebhookEvent

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class WebhookEndpointCreate(BaseModel):
    """Payload to register a new webhook endpoint."""

    url: HttpUrl = Field(..., description="HTTPS URL to receive webhook POST requests.")
    secret: str = Field(
        ...,
        min_length=16,
        max_length=255,
        description="Shared secret used to compute the HMAC-SHA256 signature header.",
    )
    description: str | None = Field(None, max_length=512, description="Optional human-readable label.")
    events: list[str] = Field(
        default_factory=lambda: ["*"],
        description=(
            "List of event types to subscribe to. Use ['*'] to receive all events. "
            f"Valid values: {[e.value for e in WebhookEvent]}"
        ),
    )

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        valid = {e.value for e in WebhookEvent} | {"*"}
        invalid = [e for e in v if e not in valid]
        if invalid:
            raise ValueError(f"Invalid event types: {invalid}. Valid: {sorted(valid)}")
        return v


class WebhookEndpointUpdate(BaseModel):
    """Partial update for a webhook endpoint."""

    url: HttpUrl | None = None
    secret: str | None = Field(None, min_length=16, max_length=255)
    description: str | None = Field(None, max_length=512)
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        valid = {e.value for e in WebhookEvent} | {"*"}
        invalid = [e for e in v if e not in valid]
        if invalid:
            raise ValueError(f"Invalid event types: {invalid}. Valid: {sorted(valid)}")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class WebhookEndpointResponse(BaseModel):
    """Registered webhook endpoint response (secret is masked)."""

    id: int
    user_id: int
    url: str
    description: str | None
    events: list[str]
    is_active: bool
    failure_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, obj: object) -> "WebhookEndpointResponse":
        """Build response from ORM model, splitting the events string."""
        from app.models.webhook import WebhookEndpoint

        assert isinstance(obj, WebhookEndpoint)
        events_list = [e.strip() for e in obj.events.split(",")] if obj.events != "*" else ["*"]
        return cls(
            id=obj.id,
            user_id=obj.user_id,
            url=str(obj.url),
            description=obj.description,
            events=events_list,
            is_active=obj.is_active,
            failure_count=obj.failure_count,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class WebhookDeliveryResponse(BaseModel):
    """Individual webhook delivery attempt log entry."""

    id: int
    endpoint_id: int
    event: str
    status: WebhookDeliveryStatus
    http_status_code: int | None
    attempt_count: int
    error_message: str | None
    delivered_at: datetime | None
    next_retry_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookTestResponse(BaseModel):
    """Result of a manual test ping to a webhook endpoint."""

    endpoint_id: int
    url: str
    success: bool
    http_status_code: int | None
    error: str | None
    delivery_id: int
