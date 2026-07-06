"""Shared UI helpers for the AegisAPI console — Phase 11, slice 2.

Severity palette, event-table styling, chart builders, and a token-aware fetch
that centralises 401 handling so every view stays small.
"""
import altair as alt
import pandas as pd
import streamlit as st

import api

# action -> (text colour, background tint) for the ops-console severity coding
ACTION_STYLE = {
    "ALLOW":      ("#45c98a", "rgba(69,201,138,.12)"),
    "THROTTLE":   ("#e0a942", "rgba(224,169,66,.12)"),
    "RATE_LIMIT": ("#e0873f", "rgba(224,135,63,.12)"),
    "BLOCK":      ("#ef6b64", "rgba(239,107,100,.14)"),
    "QUARANTINE": ("#f2557a", "rgba(242,85,122,.16)"),
}
RISK_STYLE = {"LOW": "#45c98a", "MEDIUM": "#e0a942", "HIGH": "#ef6b64"}

_SESSION_KEYS = ("token", "refresh_token", "username", "role")

CSS = """
<style>
  .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1220px; }

  [data-testid="stMetric"] {
    background: #11242a; border: 1px solid #1d3a3e; border-radius: 12px; padding: 14px 18px;
  }
  [data-testid="stMetricLabel"] p { color: #6d8785; font-size: .76rem;
    letter-spacing: .06em; text-transform: uppercase; }

  .aegis-brand { font-family: ui-monospace, monospace; letter-spacing: .2em;
    color: #2ad3bf; font-size: .82rem; text-transform: uppercase; font-weight: 600; }
  .aegis-sub { color: #6d8785; font-family: ui-monospace, monospace;
    font-size: .8rem; letter-spacing: .04em; }
  .aegis-pill { display: inline-block; padding: 3px 11px; border-radius: 999px;
    border: 1px solid #1d3a3e; font-family: ui-monospace, monospace; font-size: .72rem;
    letter-spacing: .08em; color: #2ad3bf; background: rgba(42,211,191,.07); }

  h1, h2, h3 { letter-spacing: -.01em; }
  div[data-testid="stForm"] { border: 1px solid #1d3a3e; border-radius: 14px;
    background: #0f2127; padding: 8px 6px; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def clear_session() -> None:
    for key in _SESSION_KEYS:
        st.session_state[key] = None


def fetch(path: str, params: dict | None = None):
    """GET with the session token. On 401 clears the session and reruns (back to
    login); on other errors shows a message and returns None."""
    token = st.session_state.get("token")
    try:
        return api.get(path, token, params=params)
    except api.APIError as exc:
        if exc.status == 401:
            clear_session()
            st.rerun()
        st.error(f"API error ({exc.status}): {exc.message}")
        return None


def put(path: str, json: dict):
    """PUT with the session token; same 401/error handling as fetch()."""
    token = st.session_state.get("token")
    try:
        return api.put(path, token, json=json)
    except api.APIError as exc:
        if exc.status == 401:
            clear_session()
            st.rerun()
        st.error(f"API error ({exc.status}): {exc.message}")
        return None


def delete(path: str):
    """DELETE with the session token; same 401/error handling as fetch()."""
    token = st.session_state.get("token")
    try:
        return api.delete(path, token)
    except api.APIError as exc:
        if exc.status == 401:
            clear_session()
            st.rerun()
        st.error(f"API error ({exc.status}): {exc.message}")
        return None


def _fmt_time(ts: str) -> str:
    return ts[:19].replace("T", " ")


def events_df(logs: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "time": _fmt_time(l["timestamp"]),
            "user": l["user_id"],
            "endpoint": l["endpoint"],
            "method": l["method"],
            "risk": l["risk_score"],
            "level": l["risk_level"],
            "action": l["action"],
            "reason": l["reason"],
        }
        for l in logs
    ])


def _color_action(val: str) -> str:
    fg, bg = ACTION_STYLE.get(val, ("#a7c0be", "transparent"))
    return f"color:{fg}; background-color:{bg}; font-weight:600;"


def styled_events(df: pd.DataFrame):
    return df.style.map(_color_action, subset=["action"])


def action_chart(df: pd.DataFrame):
    counts = df["action"].value_counts().reset_index()
    counts.columns = ["action", "count"]
    order = list(ACTION_STYLE.keys())
    return (
        alt.Chart(counts)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("count:Q", title="events"),
            y=alt.Y("action:N", sort=order, title=None),
            color=alt.Color(
                "action:N",
                scale=alt.Scale(domain=order, range=[ACTION_STYLE[a][0] for a in order]),
                legend=None,
            ),
            tooltip=["action", "count"],
        )
        .properties(height=230)
    )


def risk_chart(df: pd.DataFrame):
    counts = df["level"].value_counts().reset_index()
    counts.columns = ["level", "count"]
    order = ["LOW", "MEDIUM", "HIGH"]
    return (
        alt.Chart(counts)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("level:N", sort=order, title=None),
            y=alt.Y("count:Q", title="events"),
            color=alt.Color(
                "level:N",
                scale=alt.Scale(domain=order, range=[RISK_STYLE[l] for l in order]),
                legend=None,
            ),
            tooltip=["level", "count"],
        )
        .properties(height=230)
    )
