"""Repository for WebhookEndpoint and WebhookDelivery database operations."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookDelivery, WebhookEndpoint


class WebhookEndpointRepository:
    """CRUD operations for webhook endpoint registrations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, endpoint: WebhookEndpoint) -> WebhookEndpoint:
        """Persist a new webhook endpoint."""
        self.session.add(endpoint)
        await self.session.flush()
        await self.session.refresh(endpoint)
        return endpoint

    async def get_by_id(self, endpoint_id: int) -> WebhookEndpoint | None:
        """Fetch endpoint by primary key."""
        stmt = select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id_and_user(self, endpoint_id: int, user_id: int) -> WebhookEndpoint | None:
        """Fetch endpoint enforcing ownership."""
        stmt = select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(self, user_id: int) -> Sequence[WebhookEndpoint]:
        """Fetch all endpoints for a user."""
        stmt = select(WebhookEndpoint).where(WebhookEndpoint.user_id == user_id).order_by(WebhookEndpoint.id.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_active_for_event(self, user_id: int, event: str) -> Sequence[WebhookEndpoint]:
        """Fetch active endpoints for a user that subscribe to a given event."""
        stmt = select(WebhookEndpoint).where(
            WebhookEndpoint.user_id == user_id,
            WebhookEndpoint.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        all_endpoints = result.scalars().all()
        return [ep for ep in all_endpoints if ep.subscribes_to(event)]

    async def update(self, endpoint: WebhookEndpoint, attributes: dict) -> WebhookEndpoint:
        """Apply attribute updates to an endpoint."""
        for key, value in attributes.items():
            if hasattr(endpoint, key) and value is not None:
                setattr(endpoint, key, value)
        await self.session.flush()
        await self.session.refresh(endpoint)
        return endpoint

    async def increment_failure_count(self, endpoint: WebhookEndpoint) -> None:
        """Increment failure counter; auto-disable after 10 consecutive failures."""
        endpoint.failure_count += 1
        if endpoint.failure_count >= 10:
            endpoint.is_active = False
        await self.session.flush()

    async def reset_failure_count(self, endpoint: WebhookEndpoint) -> None:
        """Reset failure counter after a successful delivery."""
        endpoint.failure_count = 0
        await self.session.flush()

    async def delete(self, endpoint: WebhookEndpoint) -> None:
        """Hard-delete a webhook endpoint and cascade deliveries."""
        await self.session.delete(endpoint)
        await self.session.flush()


class WebhookDeliveryRepository:
    """CRUD operations for webhook delivery logs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, delivery: WebhookDelivery) -> WebhookDelivery:
        """Persist a new delivery record."""
        self.session.add(delivery)
        await self.session.flush()
        await self.session.refresh(delivery)
        return delivery

    async def get_by_id(self, delivery_id: int) -> WebhookDelivery | None:
        """Fetch a delivery record by primary key."""
        stmt = select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_endpoint(
        self,
        endpoint_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[WebhookDelivery]:
        """Fetch delivery logs for a specific endpoint, newest first."""
        stmt = (
            select(WebhookDelivery)
            .where(WebhookDelivery.endpoint_id == endpoint_id)
            .order_by(WebhookDelivery.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, delivery: WebhookDelivery) -> WebhookDelivery:
        """Flush delivery state changes to the database."""
        await self.session.flush()
        await self.session.refresh(delivery)
        return delivery
