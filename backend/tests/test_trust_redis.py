from app.services.trust import (
    get_trust_score, set_trust_score, update_trust_score, restore_trust,
    DEFAULT_TRUST_SCORE,
)


async def test_default_trust_on_first_read(fake_redis):
    assert await get_trust_score(fake_redis, "newuser") == DEFAULT_TRUST_SCORE


async def test_set_clamps_to_range(fake_redis):
    await set_trust_score(fake_redis, "u", 5.0)
    assert await get_trust_score(fake_redis, "u") == 1.0
    await set_trust_score(fake_redis, "u", -5.0)
    assert await get_trust_score(fake_redis, "u") == 0.0


async def test_clean_traffic_increases_trust(fake_redis):
    await set_trust_score(fake_redis, "u", 0.70)
    assert await update_trust_score(fake_redis, "u", risk_score=0) == 0.72


async def test_medium_risk_drops_trust(fake_redis):
    await set_trust_score(fake_redis, "u", 0.70)
    assert await update_trust_score(fake_redis, "u", risk_score=40) == 0.65


async def test_high_risk_drops_trust(fake_redis):
    await set_trust_score(fake_redis, "u", 0.70)
    assert await update_trust_score(fake_redis, "u", risk_score=70) == 0.55


async def test_anomaly_penalty_stacks_on_risk(fake_redis):
    await set_trust_score(fake_redis, "u", 0.70)
    # high risk (-0.15) + anomaly (-0.20) = -0.35
    assert await update_trust_score(fake_redis, "u", risk_score=70, is_anomaly=True) == 0.35


async def test_clean_traffic_with_anomaly_still_penalized(fake_redis):
    await set_trust_score(fake_redis, "u", 0.70)
    # clean (+0.02) + anomaly (-0.20) = -0.18
    assert await update_trust_score(fake_redis, "u", risk_score=0, is_anomaly=True) == 0.52


async def test_trust_floored_at_zero(fake_redis):
    await set_trust_score(fake_redis, "u", 0.10)
    assert await update_trust_score(fake_redis, "u", risk_score=70, is_anomaly=True) == 0.0


async def test_trust_capped_at_one(fake_redis):
    await set_trust_score(fake_redis, "u", 0.99)
    assert await update_trust_score(fake_redis, "u", risk_score=0) == 1.0


async def test_restore_trust_raises_low_trust_to_baseline(fake_redis):
    await set_trust_score(fake_redis, "u", 0.10)
    assert await restore_trust(fake_redis, "u", 0.5) == 0.5
    assert await get_trust_score(fake_redis, "u") == 0.5


async def test_restore_trust_never_lowers_higher_trust(fake_redis):
    await set_trust_score(fake_redis, "u", 0.9)
    assert await restore_trust(fake_redis, "u", 0.5) == 0.9
    assert await get_trust_score(fake_redis, "u") == 0.9
