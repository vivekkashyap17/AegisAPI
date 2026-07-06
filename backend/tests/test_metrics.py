from prometheus_client import REGISTRY, generate_latest

from app.services.metrics import (
    record_ingest, record_rejection, record_policy_reload,
)


def _val(name, labels=None):
    """Current value of a metric sample, or 0.0 if it hasn't been recorded yet."""
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def test_record_ingest_increments_labelled_counter():
    before = _val("aegis_ingest_requests_total", {"action": "ALLOW", "risk_level": "LOW"})
    record_ingest("ALLOW", "LOW", 5, 0.72, False)
    after = _val("aegis_ingest_requests_total", {"action": "ALLOW", "risk_level": "LOW"})
    assert after == before + 1


def test_record_ingest_observes_risk_and_trust_histograms():
    risk_before = _val("aegis_risk_score_count")
    trust_before = _val("aegis_trust_score_count")
    record_ingest("THROTTLE", "MEDIUM", 40, 0.6, False)
    assert _val("aegis_risk_score_count") == risk_before + 1
    assert _val("aegis_trust_score_count") == trust_before + 1


def test_record_ingest_counts_anomaly_only_when_flagged():
    before = _val("aegis_anomalies_total")
    record_ingest("ALLOW", "LOW", 5, 0.7, False)
    assert _val("aegis_anomalies_total") == before  # not flagged -> unchanged
    record_ingest("RATE_LIMIT", "LOW", 5, 0.5, True)
    assert _val("aegis_anomalies_total") == before + 1


def test_record_rejection_counts_rejection_and_quarantine_action():
    rej_before = _val("aegis_quarantine_rejections_total")
    act_before = _val("aegis_ingest_requests_total", {"action": "QUARANTINE", "risk_level": "HIGH"})
    trust_before = _val("aegis_trust_score_count")
    record_rejection("HIGH", 80)
    assert _val("aegis_quarantine_rejections_total") == rej_before + 1
    assert _val("aegis_ingest_requests_total", {"action": "QUARANTINE", "risk_level": "HIGH"}) == act_before + 1
    # rejection path must NOT touch the trust histogram
    assert _val("aegis_trust_score_count") == trust_before


def test_record_policy_reload_increments():
    before = _val("aegis_policy_reloads_total")
    record_policy_reload()
    assert _val("aegis_policy_reloads_total") == before + 1


def test_metrics_exposition_contains_metric_families():
    record_ingest("ALLOW", "LOW", 5, 0.7, False)
    output = generate_latest().decode()
    assert "aegis_ingest_requests_total" in output
    assert "aegis_risk_score_bucket" in output
    assert "aegis_trust_score_bucket" in output
