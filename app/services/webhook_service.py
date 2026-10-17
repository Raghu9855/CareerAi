"""WebhookService: endpoint registration, management, delivery orchestration, and test pings."""

import json
import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.webhook_dispatcher import build_payload, dispatch_once, next_retry_at
from app.models.webhook import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint
from app.repositories.webhook_repo import WebhookDeliveryRepository, WebhookEndpointRepository
from app.schemas.webhook import WebhookEndpointCreate, WebhookEndpointUpdate

logger = get_logger("careerai.services.webhook")


class WebhookService:
    """Business operations for webhook endpoint lifecycle and delivery."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.endpoint_repo = WebhookEndpointRepository(session)
        self.delivery_repo = WebhookDeliveryRepository(session)

    # ------------------------------------------------------------------
    # Endpoint Registration
    # ------------------------------------------------------------------

    async def register_endpoint(self, user_id: int, payload: WebhookEndpointCreate) -> WebhookEndpoint:
        """Register a new webhook endpoint for a user.

        A random 32-byte URL-safe token is generated as the signing secret if the
        caller does not supply their own.
        """
        # Prevent duplicate registrations for the same URL per user
        existing = await self.endpoint_repo.list_by_user(user_id)
        url_str = str(payload.url)
        for ep in existing:
            if ep.url == url_str:
                raise ConflictError(
                    message="A webhook endpoint with this URL is already registered",
                    details={"url": url_str, "existing_id": ep.id},
                )

        events_str = ",".join(payload.events) if payload.events != ["*"] else "*"
        endpoint = WebhookEndpoint(
            user_id=user_id,
            url=url_str,
            secret=payload.secret or secrets.token_urlsafe(32),
            description=payload.description,
            events=events_str,
            is_active=True,
            failure_count=0,
        )
        created = await self.endpoint_repo.create(endpoint)
        await self.session.commit()
        logger.info(f"Registered webhook endpoint id={created.id} for user_id={user_id}")
        return created

    async def get_endpoint(self, endpoint_id: int, user_id: int) -> WebhookEndpoint:
        """Fetch a webhook endpoint enforcing ownership."""
        endpoint = await self.endpoint_repo.get_by_id_and_user(endpoint_id, user_id)
        if not endpoint:
            raise NotFoundError(
                message="Webhook endpoint not found",
                details={"endpoint_id": endpoint_id},
            )
        return endpoint

    async def list_endpoints(self, user_id: int) -> list[WebhookEndpoint]:
        """List all registered webhook endpoints for a user."""
        return list(await self.endpoint_repo.list_by_user(user_id))

    async def update_endpoint(
        self,
        endpoint_id: int,
        user_id: int,
        payload: WebhookEndpointUpdate,
    ) -> WebhookEndpoint:
        """Partial update of a webhook endpoint."""
        endpoint = await self.get_endpoint(endpoint_id, user_id)
        updates: dict[str, Any] = {}
        if payload.url is not None:
            updates["url"] = str(payload.url)
        if payload.secret is not None:
            updates["secret"] = payload.secret
        if payload.description is not None:
            updates["description"] = payload.description
        if payload.events is not None:
            updates["events"] = ",".join(payload.events) if payload.events != ["*"] else "*"
        if payload.is_active is not None:
            updates["is_active"] = payload.is_active
            if payload.is_active:
                updates["failure_count"] = 0  # re-enabling resets failure counter
        updated = await self.endpoint_repo.update(endpoint, updates)
        await self.session.commit()
        return updated

    async def delete_endpoint(self, endpoint_id: int, user_id: int) -> None:
        """Remove a webhook endpoint (and cascade-delete all its delivery logs)."""
        endpoint = await self.get_endpoint(endpoint_id, user_id)
        await self.endpoint_repo.delete(endpoint)
        await self.session.commit()
        logger.info(f"Deleted webhook endpoint id={endpoint_id} for user_id={user_id}")

    # ------------------------------------------------------------------
    # Delivery Logs
    # ------------------------------------------------------------------

    async def list_deliveries(
        self,
        endpoint_id: int,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WebhookDelivery]:
        """List delivery log entries for a user's endpoint."""
        # ownership check
        await self.get_endpoint(endpoint_id, user_id)
        return list(await self.delivery_repo.list_by_endpoint(endpoint_id, limit=limit, offset=offset))

    # ------------------------------------------------------------------
    # Event Dispatch
    # ------------------------------------------------------------------

    async def dispatch_event(
        self,
        user_id: int,
        event: str,
        data: dict[str, Any],
    ) -> list[WebhookDelivery]:
        """Dispatch an event to all active endpoints subscribed to it.

        Creates a delivery record, attempts immediate dispatch, and marks
        result accordingly. Returns list of created delivery records.
        """
        active_endpoints = await self.endpoint_repo.list_active_for_event(user_id, event)
        if not active_endpoints:
            logger.debug(f"No active webhook endpoints for user_id={user_id} event='{event}'")
            return []

        deliveries: list[WebhookDelivery] = []
        for endpoint in active_endpoints:
            delivery = await self._create_and_dispatch(endpoint, event, data)
            deliveries.append(delivery)

        await self.session.commit()
        return deliveries

    async def _create_and_dispatch(
        self,
        endpoint: WebhookEndpoint,
        event: str,
        data: dict[str, Any],
    ) -> WebhookDelivery:
        """Create a delivery record, perform the HTTP dispatch, and update its state."""
        # Create a pending delivery first
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event=event,
            payload=json.dumps(data, default=str),
            status=WebhookDeliveryStatus.PENDING,
            attempt_count=0,
        )
        delivery = await self.delivery_repo.create(delivery)

        # Build the signed envelope with the delivery id
        envelope = build_payload(event, data, delivery_id=delivery.id)
        success, http_status, message = await dispatch_once(
            url=endpoint.url,
            secret=endpoint.secret,
            payload=envelope,
        )

        if success:
            delivery.mark_success(http_status=http_status or 200, body=message)
            await self.endpoint_repo.reset_failure_count(endpoint)
        else:
            retry_at = next_retry_at(delivery.attempt_count)
            delivery.mark_failed(error=message, http_status=http_status, retry_at=retry_at)
            await self.endpoint_repo.increment_failure_count(endpoint)

        await self.delivery_repo.update(delivery)
        return delivery

    # ------------------------------------------------------------------
    # Test Ping
    # ------------------------------------------------------------------

    async def send_test_ping(self, endpoint_id: int, user_id: int) -> WebhookDelivery:
        """Fire a synthetic test event to verify connectivity."""
        endpoint = await self.get_endpoint(endpoint_id, user_id)
        test_data: dict[str, Any] = {
            "message": "CareerAI webhook test ping",
            "endpoint_id": endpoint_id,
        }
        delivery = await self._create_and_dispatch(endpoint, "webhook.test", test_data)
        await self.session.commit()
        return delivery

    # ------------------------------------------------------------------
    # Retry Support (called from background worker)
    # ------------------------------------------------------------------

    async def retry_delivery(self, delivery_id: int) -> WebhookDelivery:
        """Re-attempt a failed or retrying delivery from the background worker."""
        delivery = await self.delivery_repo.get_by_id(delivery_id)
        if not delivery:
            raise NotFoundError(
                message="Webhook delivery not found",
                details={"delivery_id": delivery_id},
            )
        endpoint = await self.endpoint_repo.get_by_id(delivery.endpoint_id)
        if not endpoint or not endpoint.is_active:
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.error_message = "Endpoint disabled or deleted; abandoning retry."
            await self.delivery_repo.update(delivery)
            await self.session.commit()
            return delivery

        stored_data: dict[str, Any] = json.loads(delivery.payload)
        envelope = build_payload(delivery.event, stored_data, delivery_id=delivery.id)
        success, http_status, message = await dispatch_once(
            url=endpoint.url,
            secret=endpoint.secret,
            payload=envelope,
        )

        if success:
            delivery.mark_success(http_status=http_status or 200, body=message)
            await self.endpoint_repo.reset_failure_count(endpoint)
        else:
            retry_at = next_retry_at(delivery.attempt_count)
            delivery.mark_failed(error=message, http_status=http_status, retry_at=retry_at)
            await self.endpoint_repo.increment_failure_count(endpoint)

        await self.delivery_repo.update(delivery)
        await self.session.commit()
        return delivery
