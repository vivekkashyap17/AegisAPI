"""Hot-reloadable policy rules.

The thresholds and deltas that drive the trust/policy engine live in a Redis
hash (`policy:rules`) instead of as code constants, so an operator can retune
them at runtime (via the admin `/policy` endpoints) without a redeploy.

`DEFAULT_RULES` is the single source of truth for both the seeded values and the
in-code fallback used by `trust.get_trust_action` / `trust.update_trust_score`
when no rules are supplied.
"""
from redis.asyncio import Redis

POLICY_RULES_KEY = "policy:rules"

DEFAULT_RULES = {
    # risk-score cutoffs (points)
    "risk_high": 60,
    "risk_moderate": 30,
    # trust-score cutoffs (0..1)
    "trust_critical": 0.3,
    "trust_low": 0.5,
    "trust_reduced": 0.6,
    # per-request trust deltas
    "delta_high_risk": -0.15,
    "delta_moderate_risk": -0.05,
    "delta_low_risk": 0.02,
    "anomaly_penalty": -0.20,
    # how long a quarantine entry lives (seconds) — consumed in the enforcement slice
    "quarantine_ttl": 3600,
}

# Keys whose values are whole numbers; everything else is treated as a float.
_INT_KEYS = {"risk_high", "risk_moderate", "quarantine_ttl"}


def _cast(key: str, value) -> float:
    """Cast a raw (string) rule value to its proper numeric type."""
    return int(value) if key in _INT_KEYS else float(value)


async def seed_default_rules(redis: Redis) -> None:
    """Populate any missing rule keys with their defaults. Idempotent — never
    overwrites a value an operator has already customised."""
    existing = await redis.hgetall(POLICY_RULES_KEY)
    missing = {k: str(v) for k, v in DEFAULT_RULES.items() if k not in existing}
    if missing:
        await redis.hset(POLICY_RULES_KEY, mapping=missing)


async def get_policy_rules(redis: Redis) -> dict:
    """Return the effective, typed rule set: stored values merged over defaults.
    A malformed stored value silently falls back to its default."""
    stored = await redis.hgetall(POLICY_RULES_KEY)
    rules = dict(DEFAULT_RULES)
    for key, raw in stored.items():
        if key in DEFAULT_RULES:
            try:
                rules[key] = _cast(key, raw)
            except (ValueError, TypeError):
                pass  # keep the default for this key
    return rules


async def update_policy_rules(redis: Redis, updates: dict) -> dict:
    """Validate and apply a partial rule update, returning the new effective rules.

    Raises ValueError on an unknown key or a non-numeric value so the caller can
    surface a 400 rather than persisting garbage.
    """
    validated = {}
    for key, value in updates.items():
        if key not in DEFAULT_RULES:
            raise ValueError(f"Unknown policy rule: {key}")
        try:
            _cast(key, value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid value for {key}: {value!r}")
        validated[key] = str(value)

    if validated:
        await redis.hset(POLICY_RULES_KEY, mapping=validated)
    return await get_policy_rules(redis)
