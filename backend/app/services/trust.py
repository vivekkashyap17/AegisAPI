from redis.asyncio import Redis

from app.services.policy_rules import DEFAULT_RULES

TRUST_SCORE_PREFIX = "trust:"
DEFAULT_TRUST_SCORE = 0.7
TRUST_SCORE_TTL = 86400  # 24 hours in seconds


async def get_trust_score(redis: Redis, user_id: str) -> float:
    key = f"{TRUST_SCORE_PREFIX}{user_id}"
    score = await redis.get(key)
    if score is None:
        await set_trust_score(redis, user_id, DEFAULT_TRUST_SCORE)
        return DEFAULT_TRUST_SCORE
    return float(score)


async def set_trust_score(redis: Redis, user_id: str, score: float):
    key = f"{TRUST_SCORE_PREFIX}{user_id}"
    clamped = max(0.0, min(1.0, score))
    await redis.setex(key, TRUST_SCORE_TTL, str(clamped))


async def update_trust_score(
    redis: Redis, user_id: str, risk_score: int, is_anomaly: bool = False,
    rules: dict | None = None,
) -> float:
    rules = rules or DEFAULT_RULES
    current = await get_trust_score(redis, user_id)

    # High risk drops trust, low risk builds it
    if risk_score >= rules["risk_high"]:
        delta = rules["delta_high_risk"]
    elif risk_score >= rules["risk_moderate"]:
        delta = rules["delta_moderate_risk"]
    else:
        delta = rules["delta_low_risk"]

    # An anomalous request is penalized on top of its risk-based delta
    if is_anomaly:
        delta += rules["anomaly_penalty"]

    new_score = current + delta
    await set_trust_score(redis, user_id, new_score)
    return round(max(0.0, min(1.0, new_score)), 4)


async def restore_trust(redis: Redis, user_id: str, baseline: float) -> float:
    """Raise a subject's trust up to `baseline` after a successful step-up re-auth.
    Never lowers an already-higher score — recovery can only help."""
    current = await get_trust_score(redis, user_id)
    new_score = max(current, baseline)
    await set_trust_score(redis, user_id, new_score)
    return round(new_score, 4)


async def get_trust_action(
    trust_score: float, risk_score: int, is_anomaly: bool = False,
    rules: dict | None = None,
) -> dict:
    rules = rules or DEFAULT_RULES
    if trust_score < rules["trust_critical"]:
        return {"action": "QUARANTINE", "reason": "Trust score critically low"}
    elif is_anomaly and risk_score >= rules["risk_high"]:
        return {"action": "QUARANTINE", "reason": "Anomalous behavior with high risk"}
    elif is_anomaly and risk_score >= rules["risk_moderate"]:
        return {"action": "BLOCK", "reason": "Anomalous behavior with elevated risk"}
    elif is_anomaly:
        return {"action": "RATE_LIMIT", "reason": "Anomalous behavior detected"}
    elif trust_score < rules["trust_low"] and risk_score >= rules["risk_high"]:
        return {"action": "BLOCK", "reason": "High risk with low trust"}
    elif trust_score < rules["trust_reduced"] and rules["risk_moderate"] <= risk_score < rules["risk_high"]:
        return {"action": "RATE_LIMIT", "reason": "Moderate risk with reduced trust"}
    elif risk_score >= rules["risk_high"]:
        return {"action": "BLOCK", "reason": "High risk detected"}
    elif risk_score >= rules["risk_moderate"]:
        return {"action": "THROTTLE", "reason": "Moderate risk detected"}
    else:
        return {"action": "ALLOW", "reason": "Normal traffic"}