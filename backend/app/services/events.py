"""Kafka event streaming — Phase 10, slice 3.

The app publishes every security decision to a Kafka topic so downstream
consumers (alerting, and later a training buffer / audit sink) can react
independently of the request path. This is additive: the synchronous pipeline
still does its Postgres write and returns as before — publishing is a
fire-and-forget side effect that must never break a request.

Kafka is optional. If `KAFKA_BOOTSTRAP_SERVERS` is unset (host-run dev, tests),
the producer is never created and `publish_security_event` is a silent no-op.
"""
import json
import logging
import os

from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

SECURITY_EVENTS_TOPIC = "security-events"

_producer: AIOKafkaProducer | None = None


def kafka_enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP_SERVERS"))


async def start_producer() -> None:
    """Start the Kafka producer if configured. Failure to connect is logged but
    never fatal — the app must boot and serve even if Kafka is down."""
    global _producer
    if not kafka_enabled():
        logger.info("Kafka disabled (KAFKA_BOOTSTRAP_SERVERS unset) — events not published")
        return
    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await _producer.start()
        logger.info("Kafka producer started")
    except Exception as exc:  # noqa: BLE001 — never let Kafka break startup
        logger.warning(f"Kafka producer failed to start: {exc}")
        _producer = None


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def publish_security_event(event: dict) -> None:
    """Publish one security event. No-op if Kafka isn't running; a publish
    failure is swallowed so it can never affect the client response."""
    if _producer is None:
        return
    try:
        await _producer.send_and_wait(SECURITY_EVENTS_TOPIC, event)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to publish security event: {exc}")
