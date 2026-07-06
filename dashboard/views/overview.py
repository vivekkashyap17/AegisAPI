"""Overview page — at-a-glance status + a preview of recent decisions."""
import streamlit as st

import ui


def render() -> None:
    st.subheader("🛰️ Overview")

    data = ui.fetch("/logs", params={"limit": 50})
    if data is None:
        return

    logs = data["logs"]
    actions = [l["action"] for l in logs]
    threats = sum(a in ("BLOCK", "QUARANTINE") for a in actions)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Audit events", f"{data['total']:,}")
    c2.metric("In recent sample", len(logs))
    c3.metric("Threats (recent)", threats)
    c4.metric("Your role", (st.session_state.get("role") or "—").upper())

    st.divider()
    st.markdown("**Most recent decisions**")
    if not logs:
        st.info("No events yet — send some traffic through the gateway to populate the console.")
        return
    df = ui.events_df(logs).head(10)
    st.dataframe(ui.styled_events(df), use_container_width=True, hide_index=True)
