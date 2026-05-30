from redis.asyncio import Redis

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


async def update_trust_score(redis: Redis, user_id: str, risk_score: int) -> float:
    current = await get_trust_score(redis, user_id)

    # High risk drops trust, low risk builds it
    if risk_score >= 60:
        delta = -0.15
    elif risk_score >= 30:
        delta = -0.05
    else:
        delta = +0.02

    new_score = current + delta
    await set_trust_score(redis, user_id, new_score)
    return round(max(0.0, min(1.0, new_score)), 4)


async def get_trust_action(trust_score: float, risk_score: int) -> dict:
    if trust_score < 0.3:
        return {"action": "QUARANTINE", "reason": "Trust score critically low"}
    elif trust_score < 0.5 and risk_score >= 60:
        return {"action": "BLOCK", "reason": "High risk with low trust"}
    elif trust_score < 0.6 and risk_score >= 30:
        return {"action": "RATE_LIMIT", "reason": "Moderate risk with reduced trust"}
    elif risk_score >= 60:
        return {"action": "BLOCK", "reason": "High risk detected"}
    elif risk_score >= 30:
        return {"action": "THROTTLE", "reason": "Moderate risk detected"}
    else:
        return {"action": "ALLOW", "reason": "Normal traffic"}