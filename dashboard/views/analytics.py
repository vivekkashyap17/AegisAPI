"""Trust & analytics — action mix, risk distribution, and the riskiest users."""
import pandas as pd
import streamlit as st

import ui


def render() -> None:
    st.subheader("📊 Trust & analytics")

    data = ui.fetch("/logs", params={"limit": 100})
    if data is None:
        return
    logs = data["logs"]
    if not logs:
        st.info("No events yet — send some traffic through the gateway to populate analytics.")
        return

    df = ui.events_df(logs)
    total = len(df)
    allowed = int((df["action"] == "ALLOW").sum())
    throttled = int(df["action"].isin(["THROTTLE", "RATE_LIMIT"]).sum())
    threats = int(df["action"].isin(["BLOCK", "QUARANTINE"]).sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sample", total)
    m2.metric("Allowed", allowed)
    m3.metric("Throttled", throttled)
    m4.metric(
        "Threats", threats,
        delta=f"{threats / total * 100:.0f}% of sample" if total else None,
        delta_color="inverse",
    )
    st.caption(f"based on the {total} most recent events  ·  {data['total']:,} total in DB")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("**Policy action mix**")
        st.altair_chart(ui.action_chart(df), use_container_width=True)
    with right:
        st.markdown("**Risk level distribution**")
        st.altair_chart(ui.risk_chart(df), use_container_width=True)

    st.divider()
    st.markdown("**Top users by threat activity**")
    threat_df = df[df["action"].isin(["BLOCK", "QUARANTINE"])]
    if threat_df.empty:
        st.info("No BLOCK / QUARANTINE events in this sample.")
        return

    top = (
        threat_df.groupby("user").size().reset_index(name="threats")
        .sort_values("threats", ascending=False).head(5)
    )
    rows = []
    for _, r in top.iterrows():
        trust = ui.fetch(f"/trust/{r['user']}")
        rows.append({
            "user": r["user"],
            "threats": int(r["threats"]),
            "trust score": trust["trust_score"] if trust else None,
            "trust level": trust["trust_level"] if trust else None,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
