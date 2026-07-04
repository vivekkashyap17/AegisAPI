from app.services.scoring import calculate_risk_score


def test_clean_traffic_is_low(make_event):
    r = calculate_risk_score(make_event(response_time=20, status_code=200,
                                        payload_size=100, endpoint="/items"))
    assert r["risk_score"] == 0
    assert r["risk_level"] == "LOW"


def test_slow_response_adds_30(make_event):
    r = calculate_risk_score(make_event(response_time=150))
    assert r["risk_score"] == 30
    assert r["risk_level"] == "MEDIUM"


def test_response_time_boundary_100_not_flagged(make_event):
    # rule is strictly > 100
    assert calculate_risk_score(make_event(response_time=100))["risk_score"] == 0
    assert calculate_risk_score(make_event(response_time=101))["risk_score"] == 30


def test_server_error_adds_25(make_event):
    r = calculate_risk_score(make_event(status_code=500))
    assert r["risk_score"] == 25
    assert r["risk_level"] == "LOW"  # 25 < 30


def test_large_payload_adds_20(make_event):
    assert calculate_risk_score(make_event(payload_size=2000))["risk_score"] == 20
    assert calculate_risk_score(make_event(payload_size=1000))["risk_score"] == 0  # strictly > 1000


def test_sensitive_endpoint_adds_15(make_event):
    for ep in ("/login", "/admin", "/payment"):
        assert calculate_risk_score(make_event(endpoint=ep))["risk_score"] == 15
    assert calculate_risk_score(make_event(endpoint="/items"))["risk_score"] == 0


def test_high_boundary_60_is_high(make_event):
    # 25 (error) + 20 (payload) + 15 (sensitive) = 60, with response_time <= 100
    r = calculate_risk_score(make_event(response_time=50, status_code=500,
                                        payload_size=2000, endpoint="/login"))
    assert r["risk_score"] == 60
    assert r["risk_level"] == "HIGH"


def test_max_combo(make_event):
    r = calculate_risk_score(make_event(response_time=200, status_code=500,
                                        payload_size=5000, endpoint="/payment"))
    assert r["risk_score"] == 90
    assert r["risk_level"] == "HIGH"
