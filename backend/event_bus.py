"""
event_bus.py - Real-Time Event Dispatch & Streaming (Kafka + SSE)

Manages on-set continuity event publishing to Confluent Cloud Kafka topic
and local real-time Server-Sent Events (SSE) broadcasting for crew feeds.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from confluent_kafka import Consumer, Producer
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

KAFKA_TOPIC = os.getenv("CONFLUENT_TOPIC", "flawless-take-events")
_producer: Producer | None = None
_alert_subscribers: set[asyncio.Queue[str]] = set()

router = APIRouter(tags=["Alerts & Events"])


def get_producer() -> Producer | None:
    """Return a cached Producer, or None if Confluent credentials are not set."""
    global _producer
    if _producer is not None:
        return _producer
    bootstrap = os.getenv("CONFLUENT_BOOTSTRAP_SERVERS")
    api_key = os.getenv("CONFLUENT_API_KEY")
    api_secret = os.getenv("CONFLUENT_API_SECRET")
    if not all([bootstrap, api_key, api_secret]):
        return None
    _producer = Producer(
        {
            "bootstrap.servers": bootstrap,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
        }
    )
    return _producer


def broadcast_event(payload: dict) -> None:
    """Broadcast an alert payload to all connected SSE browser clients."""
    data_str = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    dead = set()
    for q in _alert_subscribers:
        try:
            q.put_nowait(data_str)
        except Exception:
            dead.add(q)
    _alert_subscribers.difference_update(dead)


def publish_event(payload: dict) -> None:
    """Serialize payload to JSON, broadcast locally via SSE, and produce to Kafka."""
    broadcast_event(payload)
    producer = get_producer()
    if producer is None:
        logger.debug("Kafka producer not configured — skipping event publish.")
        return

    def _on_delivery(err, msg):
        if err:
            logger.error("Kafka delivery failed: %s", err)
        else:
            logger.info("Kafka event delivered → %s [%d]", msg.topic(), msg.partition())

    try:
        producer.produce(
            topic=KAFKA_TOPIC,
            value=json.dumps(payload, ensure_ascii=False).encode(),
            on_delivery=_on_delivery,
        )
        producer.poll(0)  # trigger delivery callbacks without blocking
    except Exception:
        logger.exception("Kafka produce() raised unexpectedly")


def make_consumer() -> Consumer | None:
    """Create a fresh Kafka Consumer. Returns None if credentials are absent."""
    bootstrap = os.getenv("CONFLUENT_BOOTSTRAP_SERVERS")
    api_key = os.getenv("CONFLUENT_API_KEY")
    api_secret = os.getenv("CONFLUENT_API_SECRET")
    if not all([bootstrap, api_key, api_secret]):
        return None
    c = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "group.id": f"flawless-alerts-{int(time.time())}",  # unique group → always read latest
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }
    )
    c.subscribe([KAFKA_TOPIC])
    return c


async def sse_generator(request: Request):
    """Yield SSE-formatted strings without blocking threads or event loop."""
    q: asyncio.Queue[str] = asyncio.Queue()
    _alert_subscribers.add(q)
    yield ": heartbeat\n\n"
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(q.get(), timeout=10.0)
                yield data
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _alert_subscribers.discard(q)


@router.get("/api/alerts")
async def alerts(request: Request):
    """
    Server-Sent Events stream. Connect with EventSource('/api/alerts').
    Broadcasts real-time events to connected browser tabs without blocking.
    """
    return StreamingResponse(
        sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Backwards compatibility aliases
_get_producer = get_producer
_broadcast_event = broadcast_event
_publish_event = publish_event
_make_consumer = make_consumer
_sse_generator = sse_generator
