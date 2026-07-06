"""Audit log browser — filter the persisted decisions and inspect any one."""
import streamlit as st

import ui


def render() -> None:
    st.subheader("🗒️ Audit log browser")

    with st.form("log_filters"):
        c1, c2, c3, c4 = st.columns([2, 1.3, 1.3, 1.4])
        user = c1.text_input("User ID")
        action = c2.selectbox("Action", ["Any", "ALLOW", "THROTTLE", "RATE_LIMIT", "BLOCK", "QUARANTINE"])
        level = c3.selectbox("Risk level", ["Any", "LOW", "MEDIUM", "HIGH"])
        limit = c4.slider("Limit", 10, 100, 50, step=10)
        st.form_submit_button("Search", use_container_width=True)

    params: dict = {"limit": limit}
    if user.strip():
        params["user_id"] = user.strip()
    if action != "Any":
        params["action"] = action
    if level != "Any":
        params["risk_level"] = level

    data = ui.fetch("/logs", params=params)
    if data is None:
        return

    logs = data["logs"]
    st.caption(f"{data['count']} shown  ·  {data['total']:,} match the filters")
    if not logs:
        st.info("No events match these filters.")
        return

    df = ui.events_df(logs)
    st.dataframe(ui.styled_events(df), use_container_width=True, hide_index=True, height=420)

    st.markdown("**Inspect an event**")
    id_map = {
        f"{l['timestamp'][:19].replace('T', ' ')} · {l['user_id']} · {l['action']}": l["id"]
        for l in logs
    }
    choice = st.selectbox("Pick an event to see its full record", ["—"] + list(id_map.keys()))
    if choice != "—":
        detail = ui.fetch(f"/logs/{id_map[choice]}")
        if detail:
            st.json(detail)
