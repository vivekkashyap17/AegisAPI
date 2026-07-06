"""Live threat monitor — decisions streaming in, auto-refreshing.

Uses a native st.fragment with run_every so only the feed re-polls on the
interval, not the whole page.
"""
from datetime import datetime

import streamlit as st

import ui


def render() -> None:
    st.subheader("📡 Live threat monitor")

    c1, c2, _ = st.columns([1, 1, 2])
    auto = c1.toggle("Auto-refresh (5s)", value=True)
    window = c2.selectbox("Window", [25, 50, 100], index=0)
    run_every = 5 if auto else None

    @st.fragment(run_every=run_every)
    def feed() -> None:
        data = ui.fetch("/logs", params={"limit": window})
        if data is None:
            return
        logs = data["logs"]

        actions = [l["action"] for l in logs]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("In view", len(logs))
        m2.metric("Allowed", sum(a == "ALLOW" for a in actions))
        m3.metric("Throttled", sum(a in ("THROTTLE", "RATE_LIMIT") for a in actions))
        m4.metric("Threats", sum(a in ("BLOCK", "QUARANTINE") for a in actions))

        st.caption(
            f"updated {datetime.now():%H:%M:%S}"
            f"{'  ·  live' if run_every else '  ·  paused'}"
            f"  ·  {data['total']:,} total in DB"
        )
        if not logs:
            st.info("No events yet — send some traffic through the gateway.")
            return
        df = ui.events_df(logs)
        st.dataframe(ui.styled_events(df), use_container_width=True, hide_index=True, height=460)

    feed()
