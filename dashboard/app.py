"""AegisAPI Security Operations Console — Phase 11.

  slice 1: foundation — login + dark ops-console theme.
  slice 2: monitoring — live monitor, audit log browser, analytics (this slice).
"""
import streamlit as st

import api
import ui
from views import analytics, logs, monitor, overview

st.set_page_config(
    page_title="AegisAPI Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="auto",
)
ui.inject_css()


def init_state() -> None:
    for key in ("token", "refresh_token", "username", "role"):
        st.session_state.setdefault(key, None)


def login_view() -> None:
    left, mid, right = st.columns([1, 1.3, 1])
    with mid:
        st.markdown("<div class='aegis-brand'>AEGISAPI</div>", unsafe_allow_html=True)
        st.markdown("## 🛡️ Security Operations Console")
        st.markdown(
            "<div class='aegis-sub'>Sign in to monitor traffic, trust, and policy decisions.</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            try:
                access, refresh = api.login(username, password)
                profile = api.me(access)
                st.session_state.token = access
                st.session_state.refresh_token = refresh
                st.session_state.username = profile.get("username")
                st.session_state.role = profile.get("role")
                st.rerun()
            except api.APIError as exc:
                if exc.status == 401:
                    st.error("Invalid credentials.")
                elif exc.status == 0:
                    st.error(exc.message)
                else:
                    st.error(f"Login failed ({exc.status}): {exc.message}")


def sidebar() -> None:
    with st.sidebar:
        st.markdown("<div class='aegis-brand'>AEGISAPI</div>", unsafe_allow_html=True)
        st.markdown("<div class='aegis-sub'>Security Operations Console</div>", unsafe_allow_html=True)
        st.divider()
        role = (st.session_state.get("role") or "").upper()
        st.markdown(
            f"<span class='aegis-pill'>{role}</span>&nbsp;&nbsp;"
            f"<span style='color:#a7c0be'>{st.session_state.get('username')}</span>",
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("Log out", use_container_width=True):
            ui.clear_session()
            st.rerun()
        st.divider()


init_state()
if not st.session_state.token:
    login_view()
else:
    sidebar()
    pages = [
        st.Page(overview.render, title="Overview", icon="🛰️", url_path="overview", default=True),
        st.Page(monitor.render, title="Live Monitor", icon="📡", url_path="monitor"),
        st.Page(logs.render, title="Audit Logs", icon="🗒️", url_path="logs"),
        st.Page(analytics.render, title="Analytics", icon="📊", url_path="analytics"),
    ]
    st.navigation(pages).run()
