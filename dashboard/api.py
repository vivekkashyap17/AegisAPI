"""Thin API client for the AegisAPI console (Phase 11, slice 1).

Runs server-side inside the Streamlit process, so calls go straight to the app
over the internal network (default http://app:8000) — no browser CORS, and the
JWT never leaves the server. Every call raises APIError on failure so the UI can
render a clean message instead of a traceback.
"""
import os

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://app:8000")
API_PREFIX = "/api/v1"
TIMEOUT = 10


class APIError(Exception):
    """status 0 = couldn't reach the API; otherwise the HTTP status."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


def _url(path: str) -> str:
    return f"{API_BASE_URL}{API_PREFIX}{path}"


def _detail(resp) -> str:
    try:
        return resp.json().get("detail", resp.text)
    except Exception:  # noqa: BLE001
        return resp.text or f"HTTP {resp.status_code}"


def _request(method: str, path: str, token: str | None = None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = requests.request(method, _url(path), headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise APIError(0, f"Cannot reach API at {API_BASE_URL} ({exc})")
    if resp.status_code >= 400:
        raise APIError(resp.status_code, _detail(resp))
    return resp.json()


def login(username: str, password: str):
    """OAuth2 password grant → (access_token, refresh_token)."""
    body = _request("POST", "/auth/login", data={"username": username, "password": password})
    return body["access_token"], body["refresh_token"]


def me(token: str) -> dict:
    return _request("GET", "/auth/me", token=token)


def get(path: str, token: str, params: dict | None = None):
    return _request("GET", path, token=token, params=params)


def put(path: str, token: str, json: dict | None = None):
    return _request("PUT", path, token=token, json=json)


def delete(path: str, token: str):
    return _request("DELETE", path, token=token)
