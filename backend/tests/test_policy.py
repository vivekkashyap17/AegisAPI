import pytest
from app.services.trust import get_trust_action


@pytest.mark.parametrize("trust,risk,is_anomaly,expected", [
    # --- no anomaly, risk-only ---
    (0.9, 10, False, "ALLOW"),
    (0.9, 40, False, "THROTTLE"),
    (0.9, 70, False, "BLOCK"),
    # --- trust floor beats everything ---
    (0.2, 10, False, "QUARANTINE"),
    (0.2, 70, True,  "QUARANTINE"),
    # --- anomaly escalation rows ---
    (0.9, 10, True,  "RATE_LIMIT"),
    (0.9, 40, True,  "BLOCK"),
    (0.9, 70, True,  "QUARANTINE"),
    # --- reduced-trust bands (no anomaly) ---
    (0.45, 70, False, "BLOCK"),        # trust<0.5 AND risk>=60
    (0.55, 40, False, "RATE_LIMIT"),   # trust<0.6 AND 30<=risk<60
    (0.55, 70, False, "BLOCK"),        # trust<0.6 but high risk still BLOCKs (no downgrade)
])
async def test_policy_matrix(trust, risk, is_anomaly, expected):
    result = await get_trust_action(trust, risk, is_anomaly)
    assert result["action"] == expected


async def test_reason_is_populated():
    result = await get_trust_action(0.9, 70, True)
    assert result["action"] == "QUARANTINE"
    assert isinstance(result["reason"], str) and result["reason"]


# Regression guard: a reduced-trust user (band [0.5, 0.6)) at high risk must not be
# downgraded to the lighter RATE_LIMIT — the reduced-trust rule is scoped to the
# moderate band (30 <= risk < 60), so high risk still resolves to BLOCK.
async def test_reduced_trust_high_risk_still_blocks():
    assert (await get_trust_action(0.55, 70, False))["action"] == "BLOCK"
    assert (await get_trust_action(0.55, 40, False))["action"] == "RATE_LIMIT"
