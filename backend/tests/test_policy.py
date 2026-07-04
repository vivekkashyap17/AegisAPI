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
    (0.55, 40, False, "RATE_LIMIT"),   # trust<0.6 AND risk>=30
])
async def test_policy_matrix(trust, risk, is_anomaly, expected):
    result = await get_trust_action(trust, risk, is_anomaly)
    assert result["action"] == expected


async def test_reason_is_populated():
    result = await get_trust_action(0.9, 70, True)
    assert result["action"] == "QUARANTINE"
    assert isinstance(result["reason"], str) and result["reason"]


# NOTE (surfaced to maintainer): the `trust < 0.6 AND risk >= 30` rule is evaluated
# BEFORE the absolute `risk >= 60 -> BLOCK` rule, so a user with trust in [0.5, 0.6)
# and risk >= 60 gets the *lighter* RATE_LIMIT instead of BLOCK — i.e. lower trust
# yields a less severe action here. This test pins the CURRENT behavior; if the
# ordering is fixed, update the expected value to "BLOCK".
async def test_trust_band_ordering_current_behavior():
    result = await get_trust_action(0.55, 70, False)
    assert result["action"] == "RATE_LIMIT"
