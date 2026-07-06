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
    "ALLOW":      ("#34d399", "rgba(52,211,153,.12)"),
    "THROTTLE":   ("#fbbf24", "rgba(251,191,36,.12)"),
    "RATE_LIMIT": ("#fb923c", "rgba(251,146,60,.12)"),
    "BLOCK":      ("#f87171", "rgba(248,113,113,.14)"),
    "QUARANTINE": ("#f472b6", "rgba(244,114,182,.16)"),
}
RISK_STYLE = {"LOW": "#34d399", "MEDIUM": "#fbbf24", "HIGH": "#f87171"}

_SESSION_KEYS = ("token", "refresh_token", "username", "role")

CSS = """
<style>
  /* Streamlit floats a header bar over the page top; make it transparent and
     push content down so the AEGISAPI lockup is never clipped by it. */
  [data-testid="stHeader"] { background: transparent; }
  .block-container { padding-top: 3.6rem; padding-bottom: 3rem; max-width: 1200px; }

  /* metric cards */
  [data-testid="stMetric"] {
    background: #1e293b; border: 1px solid #334155; border-radius: 14px;
    padding: 16px 20px; transition: border-color .15s ease;
  }
  [data-testid="stMetric"]:hover { border-color: #3f5a7d; }
  [data-testid="stMetricLabel"] p { color: #94a3b8; font-size: .74rem;
    letter-spacing: .07em; text-transform: uppercase; }
  [data-testid="stMetricValue"] { color: #f1f5f9; }

  /* brand lockup — line-height + padding so the caps are never cut off */
  .aegis-brand { display: inline-flex; align-items: center; gap: .45rem;
    font-family: ui-monospace, "SFMono-Regular", monospace; letter-spacing: .22em;
    color: #38bdf8; font-size: .9rem; text-transform: uppercase; font-weight: 700;
    line-height: 1.7; padding: 2px 0 4px; }
  .aegis-brand::before { content: "🛡"; letter-spacing: 0; font-size: 1.05rem; }
  .aegis-sub { color: #94a3b8; font-family: ui-monospace, monospace;
    font-size: .8rem; letter-spacing: .03em; }
  .aegis-pill { display: inline-block; padding: 3px 12px; border-radius: 999px;
    border: 1px solid #38bdf8; font-family: ui-monospace, monospace; font-size: .7rem;
    letter-spacing: .09em; color: #38bdf8; background: rgba(56,189,248,.10); }

  /* sidebar */
  [data-testid="stSidebar"] { border-right: 1px solid #1e293b; }
  [data-testid="stSidebar"] > div:first-child { padding-top: 1.6rem; }

  h1, h2, h3 { letter-spacing: -.01em; color: #f1f5f9; }

  /* forms as cards */
  div[data-testid="stForm"] { border: 1px solid #334155; border-radius: 16px;
    background: #172033; padding: 12px 16px 6px; }

  .stButton > button, .stFormSubmitButton > button { border-radius: 10px; }
  [data-testid="stDataFrame"] { border-radius: 12px; }
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
