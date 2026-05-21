from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from app.worker import consumer
from tests.conftest import FakeModelService

pytestmark = pytest.mark.worker


class FakeMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = False
        self.nacked_requeue: bool | None = None

    async def ack(self) -> None:
        self.acked = True

    async def nack(self, *, requeue: bool) -> None:
        self.nacked_requeue = requeue


@pytest.mark.anyio
async def test_handle_message_acks_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_process_job(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(consumer, "process_job", fake_process_job)
    message = FakeMessage(json.dumps({"job_id": str(uuid4())}).encode("utf-8"))

    await consumer.handle_message(
        message,
        model_service=FakeModelService(),
        session_factory=None,
        chunk_size=1000,
    )

    assert message.acked is True
    assert message.nacked_requeue is None


@pytest.mark.anyio
async def test_handle_message_requeues_transient_db_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_process_job(*_args, **_kwargs) -> None:
        raise OperationalError("select 1", {}, RuntimeError("db down"))

    monkeypatch.setattr(consumer, "process_job", fake_process_job)
    message = FakeMessage(json.dumps({"job_id": str(uuid4())}).encode("utf-8"))

    await consumer.handle_message(
        message,
        model_service=FakeModelService(),
        session_factory=None,
        chunk_size=1000,
    )

    assert message.acked is False
    assert message.nacked_requeue is True


@pytest.mark.anyio
async def test_handle_message_drops_malformed_payload() -> None:
    message = FakeMessage(b"{not-json")

    await consumer.handle_message(
        message,
        model_service=FakeModelService(),
        session_factory=None,
        chunk_size=1000,
    )

    assert message.acked is False
    assert message.nacked_requeue is False
