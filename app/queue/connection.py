from __future__ import annotations

import json
from uuid import UUID

from app.config import Settings

try:
    import aio_pika
    from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    aio_pika = None  # type: ignore[assignment]
    AbstractChannel = object  # type: ignore[assignment,misc]
    AbstractQueue = object  # type: ignore[assignment,misc]
    AbstractRobustConnection = object  # type: ignore[assignment,misc]


class RabbitConnection:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.rabbitmq_url
        self.queue_name = settings.rabbitmq_queue_batch
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None

    @property
    def channel(self) -> AbstractChannel:
        if self._channel is None:
            raise RuntimeError("RabbitMQ channel is not connected")
        return self._channel

    @property
    def queue(self) -> AbstractQueue:
        if self._queue is None:
            raise RuntimeError("RabbitMQ queue is not declared")
        return self._queue

    async def connect(self) -> None:
        if aio_pika is None:
            raise RuntimeError("aio-pika is required for RabbitMQ support")
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._queue = await self._channel.declare_queue(self.queue_name, durable=True)

    async def publish_job(self, job_id: UUID) -> None:
        if aio_pika is None:
            raise RuntimeError("aio-pika is required for RabbitMQ support")
        body = json.dumps({"job_id": str(job_id)}).encode("utf-8")
        message = aio_pika.Message(
            body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.channel.default_exchange.publish(message, routing_key=self.queue_name)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._queue = None
