"""Quarantine registry — the enforcement half of the policy engine.

A QUARANTINE verdict from `trust.get_trust_action` is made real here: the subject
(`event.user_id`) is written to a Redis key `quarantine:<user_id>` with a TTL
(from the `quarantine_ttl` policy rule). While that key exists, `/ingest` rejects
the subject's events up front instead of scoring them.

Keyed on the traffic *subject*, not the authenticated API caller — trust scores
and quarantine both track the monitored entity, not the operator posting events.
"""
import json
from datetime import datetime

from redis.asyncio import Redis

QUARANTINE_PREFIX = "quarantine:"


def _key(user_id: str) -> str:
    return f"{QUARANTINE_PREFIX}{user_id}"


async def quarantine_user(redis: Redis, user_id: str, ttl: int, reason: str) -> None:
    """Quarantine a subject for `ttl` seconds. Idempotent — re-quarantining
    refreshes the TTL and reason."""
    payload = json.dumps({
        "reason": reason,
        "quarantined_at": datetime.utcnow().isoformat(),
    })
    await redis.setex(_key(user_id), ttl, payload)


async def is_quarantined(redis: Redis, user_id: str) -> bool:
    return bool(await redis.exists(_key(user_id)))


async def get_quarantine(redis: Redis, user_id: str) -> dict | None:
    """Return quarantine info (reason, quarantined_at) plus remaining TTL as
    `retry_after`, or None if the subject isn't quarantined."""
    key = _key(user_id)
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        info = json.loads(raw)
    except (ValueError, TypeError):
        info = {}
    ttl = await redis.ttl(key)
    info["retry_after"] = ttl if ttl and ttl > 0 else None
    return info


async def release_user(redis: Redis, user_id: str) -> bool:
    """Lift a subject's quarantine. Returns True if they were quarantined."""
    return bool(await redis.delete(_key(user_id)))
