"""AegisAPI Security Operations Console — Phase 11, slice 1 (foundation).

Login + session-held JWT + an authenticated home. Monitoring, log browsing,
analytics, and admin controls arrive in slices 2-3.
"""
import streamlit as st

import api

st.set_page_config(
    page_title="AegisAPI Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
  .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }

  /* metric tiles as ops-console panels */
  [data-testid="stMetric"] {
    background: #11242a;
    border: 1px solid #1d3a3e;
    border-radius: 12px;
    padding: 16px 18px;
  }
  [data-testid="stMetricLabel"] p { color: #6d8785; font-size: .78rem;
    letter-spacing: .06em; text-transform: uppercase; }

  /* brand + pills */
  .aegis-brand { font-family: ui-monospace, monospace; letter-spacing: .2em;
    color: #2ad3bf; font-size: .82rem; text-transform: uppercase; font-weight: 600; }
  .aegis-sub { color: #6d8785; font-family: ui-monospace, monospace;
    font-size: .8rem; letter-spacing: .04em; }
  .aegis-pill { display: inline-block; padding: 3px 11px; border-radius: 999px;
    border: 1px solid #1d3a3e; font-family: ui-monospace, monospace; font-size: .72rem;
    letter-spacing: .08em; color: #2ad3bf; background: rgba(42,211,191,.07); }

  h1, h2, h3 { letter-spacing: -.01em; }
  div[data-testid="stForm"] { border: 1px solid #1d3a3e; border-radius: 14px;
    background: #0f2127; padding: 8px 4px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

_SESSION_KEYS = ("token", "refresh_token", "username", "role")


def init_state() -> None:
    for key in _SESSION_KEYS:
        st.session_state.setdefault(key, None)


def logout() -> None:
    for key in _SESSION_KEYS:
        st.session_state[key] = None


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


def top_bar() -> None:
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            "<span class='aegis-brand'>AEGISAPI</span>"
            "<span class='aegis-sub'>&nbsp;&nbsp;·&nbsp;&nbsp;Security Operations Console</span>",
            unsafe_allow_html=True,
        )
    with right:
        role = (st.session_state.role or "").upper()
        st.markdown(
            f"<div style='text-align:right; margin-bottom:6px'>"
            f"<span class='aegis-pill'>{role}</span>&nbsp;&nbsp;"
            f"<span style='color:#a7c0be'>{st.session_state.username}</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("Log out", use_container_width=True):
            logout()
            st.rerun()


def home_view() -> None:
    top_bar()
    st.divider()

    total = None
    api_ok = True
    try:
        logs = api.get("/logs", st.session_state.token, params={"limit": 1})
        total = logs.get("total", 0)
    except api.APIError as exc:
        if exc.status == 401:
            logout()
            st.rerun()
        api_ok = False
        st.error(f"API error: {exc.message}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Audit events", f"{total:,}" if total is not None else "—")
    c2.metric("Your role", (st.session_state.role or "—").upper())
    c3.metric("API", "Connected" if api_ok else "Unreachable")

    st.divider()
    st.subheader("Console")
    st.info(
        "Foundation ready — authenticated and connected to the API. Coming next:\n\n"
        "- **Live threat monitor** — decisions streaming in\n"
        "- **Audit log browser** — search & filter\n"
        "- **Trust & analytics** — charts\n"
        "- **Admin controls** — policy rules & quarantine"
    )


init_state()
if st.session_state.token:
    home_view()
else:
    login_view()
