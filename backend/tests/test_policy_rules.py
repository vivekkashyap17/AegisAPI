import pytest

from app.services.policy_rules import (
    DEFAULT_RULES, get_policy_rules, seed_default_rules, update_policy_rules,
    POLICY_RULES_KEY,
)
from app.services.trust import get_trust_action, update_trust_score, set_trust_score


async def test_get_returns_defaults_when_unseeded(fake_redis):
    assert await get_policy_rules(fake_redis) == DEFAULT_RULES


async def test_seed_populates_all_defaults(fake_redis):
    await seed_default_rules(fake_redis)
    stored = await fake_redis.hgetall(POLICY_RULES_KEY)
    assert set(stored.keys()) == set(DEFAULT_RULES.keys())


async def test_seed_preserves_existing_override(fake_redis):
    await update_policy_rules(fake_redis, {"risk_high": 80})
    await seed_default_rules(fake_redis)  # must not clobber the operator's value
    rules = await get_policy_rules(fake_redis)
    assert rules["risk_high"] == 80
    assert rules["risk_moderate"] == DEFAULT_RULES["risk_moderate"]


async def test_values_are_typed(fake_redis):
    await seed_default_rules(fake_redis)
    rules = await get_policy_rules(fake_redis)
    assert isinstance(rules["risk_high"], int)
    assert isinstance(rules["trust_low"], float)


async def test_malformed_stored_value_falls_back_to_default(fake_redis):
    await fake_redis.hset(POLICY_RULES_KEY, "risk_high", "not-a-number")
    rules = await get_policy_rules(fake_redis)
    assert rules["risk_high"] == DEFAULT_RULES["risk_high"]


async def test_update_unknown_key_raises(fake_redis):
    with pytest.raises(ValueError):
        await update_policy_rules(fake_redis, {"nope": 1})


async def test_update_bad_value_raises(fake_redis):
    with pytest.raises(ValueError):
        await update_policy_rules(fake_redis, {"risk_high": "abc"})


async def test_custom_rules_change_decision(fake_redis):
    # Lower the high-risk cutoff so a risk of 40 now counts as HIGH -> BLOCK.
    rules = await update_policy_rules(fake_redis, {"risk_high": 40})
    assert (await get_trust_action(0.9, 40, False, rules))["action"] == "BLOCK"
    # Defaults leave 40 as merely THROTTLE.
    assert (await get_trust_action(0.9, 40, False))["action"] == "THROTTLE"


async def test_step_up_trust_is_configurable(fake_redis):
    rules = await update_policy_rules(fake_redis, {"step_up_trust": 0.4})
    assert rules["step_up_trust"] == 0.4


async def test_custom_anomaly_penalty_applied(fake_redis):
    await set_trust_score(fake_redis, "u", 0.70)
    rules = await update_policy_rules(fake_redis, {"anomaly_penalty": -0.50})
    # clean (+0.02) + custom anomaly (-0.50) = -0.48 -> 0.22
    result = await update_trust_score(fake_redis, "u", risk_score=0, is_anomaly=True, rules=rules)
    assert result == 0.22
