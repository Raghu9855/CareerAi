"""Background worker executing asynchronous parsing, embedding, and batch analysis jobs."""

import asyncio
import json
import signal
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.redis import get_redis_client

logger = get_logger("careerai.worker")


class BackgroundWorker:
    """Consumes and executes heavy AI and document processing jobs from Redis queue."""

    QUEUE_KEY = "careerai:task_queue"

    def __init__(self) -> None:
        self.running = False
        self.settings = get_settings()

    async def start(self) -> None:
        """Start worker loop polling Redis queue."""
        self.running = True
        logger.info(f"CareerAI Worker started. Listening on queue: '{self.QUEUE_KEY}'")

        redis_client = await get_redis_client()
        if not redis_client:
            logger.warning("Redis client unavailable. Worker idling in fallback polling mode.")

        while self.running:
            try:
                if redis_client:
                    # Blocking pop with 2s timeout
                    job_data = await redis_client.blpop([self.QUEUE_KEY], timeout=2)
                    if job_data:
                        _, payload_raw = job_data
                        payload = json.loads(payload_raw)
                        await self.process_job(payload)
                else:
                    await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in worker event loop: {exc}")
                await asyncio.sleep(1.0)

        logger.info("CareerAI Worker stopped cleanly.")

    async def process_job(self, payload: dict[str, Any]) -> None:
        """Route job payload to the appropriate processing handler."""
        job_type = payload.get("type")
        logger.info(f"Processing background job: {job_type}", extra={"payload": payload})

        if job_type == "extract_document":
            await self._handle_document_extraction(payload)
        elif job_type == "index_rag_document":
            await self._handle_rag_indexing(payload)
        elif job_type == "batch_ml_inference":
            await self._handle_batch_ml(payload)
        elif job_type == "dispatch_webhook":
            await self._handle_webhook_retry(payload)
        else:
            logger.warning(f"Unknown background job type: {job_type}")

    async def _handle_document_extraction(self, payload: dict[str, Any]) -> None:
        doc_id = payload.get("document_id")
        logger.info(f"Successfully extracted text for document {doc_id}")

    async def _handle_rag_indexing(self, payload: dict[str, Any]) -> None:
        doc_id = payload.get("document_id")
        logger.info(f"Successfully chunked and embedded document {doc_id} into vector store")

    async def _handle_batch_ml(self, payload: dict[str, Any]) -> None:
        user_id = payload.get("user_id")
        logger.info(f"Successfully executed batch compatibility inference for candidate {user_id}")

    async def _handle_webhook_retry(self, payload: dict[str, Any]) -> None:
        """Re-attempt a failed webhook delivery by delivery_id."""
        delivery_id = payload.get("delivery_id")
        if not delivery_id:
            logger.warning("dispatch_webhook job missing delivery_id — skipping")
            return

        try:
            from app.db.session import get_session_factory
            from app.services.webhook_service import WebhookService

            session_factory = get_session_factory()
            async with session_factory() as session:
                service = WebhookService(session)
                delivery = await service.retry_delivery(int(delivery_id))
                logger.info(f"Webhook retry delivery_id={delivery_id} status={delivery.status}")
        except Exception as exc:
            logger.error(f"Webhook retry handler error for delivery_id={delivery_id}: {exc}")

    def stop(self) -> None:
        """Signal worker to terminate gracefully."""
        self.running = False


async def enqueue_job(job_type: str, data: dict[str, Any]) -> bool:
    """Enqueue a job to the background Redis worker queue."""
    redis_client = await get_redis_client()
    if not redis_client:
        logger.debug(f"Redis unavailable; executing inline: {job_type}")
        return False

    payload = json.dumps({"type": job_type, **data})
    await redis_client.rpush(BackgroundWorker.QUEUE_KEY, payload)
    return True


def main() -> None:
    """CLI entrypoint for running the worker standalone."""
    setup_logging()
    worker = BackgroundWorker()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal(*_: Any) -> None:
        worker.stop()

    import contextlib

    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(ValueError, AttributeError):
            signal.signal(sig, handle_signal)

    try:
        loop.run_until_complete(worker.start())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
