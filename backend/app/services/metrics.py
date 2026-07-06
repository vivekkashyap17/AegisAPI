"""Prometheus metrics — the instrumentation layer of observability (Phase 8).

Defines the metric objects and thin recording helpers the request pipeline calls
to expose what the policy engine is doing in aggregate. The audit log is the
per-event forensic record; these metrics are the real-time operational view,
scraped by Prometheus at `GET /metrics`.

Metric objects register on the default `prometheus_client` registry the first
time this module is imported, so they persist for the process lifetime. Counters
are named without the `_total` suffix — the client appends it in the exposition
(`aegis_ingest_requests` -> `aegis_ingest_requests_total`).
"""
from prometheus_client import Counter, Histogram

# The spine of the dashboards: every processed event, labelled by the policy
# verdict and risk band. rate() over this gives throughput and the live
# ALLOW/THROTTLE/BLOCK/QUARANTINE mix.
INGEST_REQUESTS = Counter(
    "aegis_ingest_requests",
    "Traffic events processed by /ingest, by policy action and risk level.",
    ["action", "risk_level"],
)

# Distribution of computed risk scores (0..100).
RISK_SCORE = Histogram(
    "aegis_risk_score",
    "Distribution of per-event risk scores.",
    buckets=(10, 20, 30, 40, 50, 60, 70, 80, 90, 100),
)

# Distribution of subject trust scores after each update (0..1).
TRUST_SCORE = Histogram(
    "aegis_trust_score",
    "Distribution of subject trust scores after each update.",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# Events flagged anomalous by the ML detector (Isolation Forest).
ANOMALIES = Counter(
    "aegis_anomalies",
    "Events flagged as anomalous by the ML detector.",
)

# Requests rejected up front because the subject was already quarantined.
QUARANTINE_REJECTIONS = Counter(
    "aegis_quarantine_rejections",
    "/ingest requests rejected because the subject is quarantined.",
)

# Hot reloads of the policy rule set via the admin API.
POLICY_RELOADS = Counter(
    "aegis_policy_reloads",
    "Successful policy-rule updates via PUT /policy.",
)


def record_ingest(
    action: str, risk_level: str, risk_score: float,
    trust_score: float, is_anomaly: bool,
) -> None:
    """Record a fully processed /ingest event (normal path)."""
    INGEST_REQUESTS.labels(action=action, risk_level=risk_level).inc()
    RISK_SCORE.observe(risk_score)
    TRUST_SCORE.observe(trust_score)
    if is_anomaly:
        ANOMALIES.inc()


def record_rejection(risk_level: str, risk_score: float) -> None:
    """Record an /ingest rejected up front because the subject is quarantined.

    Trust is deliberately not observed here — the rejection path never touches
    the subject's trust score.
    """
    INGEST_REQUESTS.labels(action="QUARANTINE", risk_level=risk_level).inc()
    RISK_SCORE.observe(risk_score)
    QUARANTINE_REJECTIONS.inc()


def record_policy_reload() -> None:
    """Record a successful hot reload of the policy rules."""
    POLICY_RELOADS.inc()
