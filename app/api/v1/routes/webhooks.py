"""FastAPI router for webhook endpoint registration, management, and delivery logs."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.webhook import (
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    WebhookTestResponse,
)
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/endpoints",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(requests_per_minute=30))],
    summary="Register a Webhook Endpoint",
    description=(
        "Register a new HTTPS endpoint to receive real-time event notifications. "
        "Each registered endpoint receives a unique HMAC-SHA256 signing secret to "
        "verify payload authenticity via the X-CareerAI-Signature header. "
        "Subscribe to specific event types or use '*' for all events."
    ),
)
async def register_webhook_endpoint(
    payload: WebhookEndpointCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    """Register a new webhook endpoint for the authenticated user."""
    service = WebhookService(db)
    endpoint = await service.register_endpoint(user_id=current_user.id, payload=payload)
    return WebhookEndpointResponse.from_orm_model(endpoint)


@router.get(
    "/endpoints",
    response_model=list[WebhookEndpointResponse],
    status_code=status.HTTP_200_OK,
    summary="List Webhook Endpoints",
    description="List all webhook endpoints registered by the authenticated user.",
)
async def list_webhook_endpoints(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookEndpointResponse]:
    """Retrieve all webhook endpoints for the current user."""
    service = WebhookService(db)
    endpoints = await service.list_endpoints(user_id=current_user.id)
    return [WebhookEndpointResponse.from_orm_model(ep) for ep in endpoints]


@router.get(
    "/endpoints/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Webhook Endpoint",
    description="Retrieve a specific webhook endpoint by ID.",
)
async def get_webhook_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    """Retrieve a webhook endpoint by ID (ownership enforced)."""
    service = WebhookService(db)
    endpoint = await service.get_endpoint(endpoint_id=endpoint_id, user_id=current_user.id)
    return WebhookEndpointResponse.from_orm_model(endpoint)


@router.patch(
    "/endpoints/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Webhook Endpoint",
    description="Partially update a webhook endpoint's URL, secret, event subscriptions, or active state.",
)
async def update_webhook_endpoint(
    endpoint_id: int,
    payload: WebhookEndpointUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    """Update a webhook endpoint (ownership enforced)."""
    service = WebhookService(db)
    endpoint = await service.update_endpoint(
        endpoint_id=endpoint_id,
        user_id=current_user.id,
        payload=payload,
    )
    return WebhookEndpointResponse.from_orm_model(endpoint)


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Webhook Endpoint",
    description="Permanently delete a webhook endpoint and all its delivery history.",
)
async def delete_webhook_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a webhook endpoint and cascade-delete all delivery logs."""
    service = WebhookService(db)
    await service.delete_endpoint(endpoint_id=endpoint_id, user_id=current_user.id)


@router.post(
    "/endpoints/{endpoint_id}/test",
    response_model=WebhookTestResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit(requests_per_minute=10))],
    summary="Send Test Ping",
    description=(
        "Fire a synthetic 'webhook.test' event to verify connectivity, "
        "TLS validity, and signature verification on the target endpoint."
    ),
)
async def test_webhook_endpoint(
    endpoint_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookTestResponse:
    """Send a test ping to validate endpoint connectivity."""
    service = WebhookService(db)
    delivery = await service.send_test_ping(endpoint_id=endpoint_id, user_id=current_user.id)
    endpoint = await service.get_endpoint(endpoint_id=endpoint_id, user_id=current_user.id)
    return WebhookTestResponse(
        endpoint_id=endpoint_id,
        url=endpoint.url,
        success=delivery.status.value == "success",
        http_status_code=delivery.http_status_code,
        error=delivery.error_message,
        delivery_id=delivery.id,
    )


@router.get(
    "/endpoints/{endpoint_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Delivery Logs",
    description=(
        "Retrieve the delivery attempt history for a webhook endpoint, "
        "including status, HTTP response code, error details, and retry schedule."
    ),
)
async def list_webhook_deliveries(
    endpoint_id: int,
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of delivery records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookDeliveryResponse]:
    """Retrieve delivery logs for a webhook endpoint (ownership enforced)."""
    service = WebhookService(db)
    deliveries = await service.list_deliveries(
        endpoint_id=endpoint_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return [WebhookDeliveryResponse.model_validate(d) for d in deliveries]
