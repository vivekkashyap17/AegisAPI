"""Admin controls — live policy-rules editor + quarantine management.

Admin-only. The page is only added to the nav for admins (app.py), and this
guard is defence-in-depth in case it's reached another way.
"""
import streamlit as st

import ui


def _differs(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) > 1e-9
    except (TypeError, ValueError):
        return a != b


def _policy_editor() -> None:
    data = ui.fetch("/policy")
    if data is None:
        return
    rules = data["rules"]
    st.caption(
        "Live thresholds and deltas driving the trust/policy engine. "
        "Changes hot-reload in Redis — no redeploy."
    )

    with st.form("policy_form"):
        new: dict = {}

        st.markdown("**Risk thresholds** (points)")
        c = st.columns(2)
        new["risk_high"] = c[0].number_input(
            "HIGH risk score ≥", 0, 100, int(rules["risk_high"]), 1,
            help="Risk score at or above this is HIGH.")
        new["risk_moderate"] = c[1].number_input(
            "MODERATE risk score ≥", 0, 100, int(rules["risk_moderate"]), 1,
            help="Risk score at or above this is MEDIUM.")

        st.markdown("**Trust thresholds** (0–1)")
        c = st.columns(4)
        new["trust_critical"] = c[0].number_input(
            "Critical", 0.0, 1.0, float(rules["trust_critical"]), 0.05, format="%.2f",
            help="Below this trust ⇒ QUARANTINE.")
        new["trust_low"] = c[1].number_input(
            "Low", 0.0, 1.0, float(rules["trust_low"]), 0.05, format="%.2f",
            help="Below this + high risk ⇒ BLOCK.")
        new["trust_reduced"] = c[2].number_input(
            "Reduced", 0.0, 1.0, float(rules["trust_reduced"]), 0.05, format="%.2f",
            help="Below this + moderate risk ⇒ RATE_LIMIT.")
        new["step_up_trust"] = c[3].number_input(
            "Step-up baseline", 0.0, 1.0, float(rules["step_up_trust"]), 0.05, format="%.2f",
            help="Trust restored to (at least) this after a successful step-up re-auth.")

        st.markdown("**Per-request trust deltas**")
        c = st.columns(4)
        new["delta_high_risk"] = c[0].number_input(
            "High-risk Δ", -1.0, 1.0, float(rules["delta_high_risk"]), 0.01, format="%.2f")
        new["delta_moderate_risk"] = c[1].number_input(
            "Moderate Δ", -1.0, 1.0, float(rules["delta_moderate_risk"]), 0.01, format="%.2f")
        new["delta_low_risk"] = c[2].number_input(
            "Low-risk Δ", -1.0, 1.0, float(rules["delta_low_risk"]), 0.01, format="%.2f")
        new["anomaly_penalty"] = c[3].number_input(
            "Anomaly Δ", -1.0, 1.0, float(rules["anomaly_penalty"]), 0.01, format="%.2f",
            help="Extra trust change stacked on when an event is anomalous.")

        st.markdown("**Quarantine**")
        new["quarantine_ttl"] = st.number_input(
            "TTL (seconds)", 0, 86400, int(rules["quarantine_ttl"]), 60,
            help="How long a quarantine entry lives.")

        submitted = st.form_submit_button("Apply changes", use_container_width=True, type="primary")

    if submitted:
        changed = {k: v for k, v in new.items() if _differs(v, rules[k])}
        if not changed:
            st.info("No changes to apply.")
            return
        result = ui.put("/policy", json=changed)
        if result is not None:
            st.success(f"Updated {len(changed)} rule(s): {', '.join(changed)}")
            st.rerun()


def _quarantine_manager() -> None:
    st.caption("Inspect and lift quarantines. A quarantined subject's requests are rejected at ingest.")

    recent = ui.fetch("/logs", params={"limit": 100})
    candidates = sorted(
        {l["user_id"] for l in (recent["logs"] if recent else []) if l["action"] == "QUARANTINE"}
    )
    if candidates:
        st.markdown("Recently quarantined: " + ", ".join(f"`{c}`" for c in candidates))

    target = st.text_input("User ID to inspect")
    if st.button("Check status", use_container_width=True) and target.strip():
        info = ui.fetch(f"/quarantine/{target.strip()}")
        if info is not None:
            st.session_state["q_info"] = info

    info = st.session_state.get("q_info")
    if not info:
        return

    if info["quarantined"]:
        st.error(f"🔒 **{info['user_id']}** is QUARANTINED")
        if info.get("info"):
            st.json(info["info"])
        if st.button(f"Release {info['user_id']}", type="primary"):
            result = ui.delete(f"/quarantine/{info['user_id']}")
            if result and result.get("released"):
                st.success(f"Released {info['user_id']}.")
                st.session_state["q_info"] = {
                    "user_id": info["user_id"], "quarantined": False, "info": None,
                }
                st.rerun()
    else:
        st.success(f"✓ **{info['user_id']}** is not quarantined.")


def render() -> None:
    if st.session_state.get("role") != "admin":
        st.warning("Admin access required.")
        return
    st.subheader("⚙️ Admin controls")
    tab_policy, tab_quarantine = st.tabs(["Policy rules", "Quarantine"])
    with tab_policy:
        _policy_editor()
    with tab_quarantine:
        _quarantine_manager()
