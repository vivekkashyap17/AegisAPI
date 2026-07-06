"""Security-event alert consumer — Phase 10, slice 3.

A standalone worker (its own compose service, same image as the app) that reads
the `security-events` stream and reacts independently of the request path. This
demonstrates the publish-once / consume-many payoff: the app just emits events;
this consumer decides what's worth alerting on, without the app knowing or
waiting.

Run:  python -m app.workers.alert_consumer
"""
import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaConsumer

from app.services.events import SECURITY_EVENTS_TOPIC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aegis.alerts")

# Actions worth raising an operator alert for.
ALERT_ACTIONS = {"BLOCK", "QUARANTINE", "RATE_LIMIT"}


async def run() -> None:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    consumer = AIOKafkaConsumer(
        SECURITY_EVENTS_TOPIC,
        bootstrap_servers=bootstrap,
        group_id="aegis-alerts",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info(f"Alert consumer listening on '{SECURITY_EVENTS_TOPIC}' via {bootstrap}")

    seen = 0
    alerts = 0
    try:
        async for msg in consumer:
            event = msg.value
            seen += 1
            action = event.get("action")
            if action in ALERT_ACTIONS:
                alerts += 1
                logger.warning(
                    f"ALERT [{action}] user={event.get('user_id')} "
                    f"risk={event.get('risk_score')} trust={event.get('trust_score')} "
                    f"reason={event.get('reason')!r}  (alerts {alerts}/{seen})"
                )
            else:
                logger.info(
                    f"event user={event.get('user_id')} action={action}  (seen {seen})"
                )
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(run())
