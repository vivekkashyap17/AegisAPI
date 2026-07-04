import pytest
import fakeredis

from app.models.traffic import TrafficEvent
from app.services import anomaly


@pytest.fixture
def make_event():
    """Factory for a TrafficEvent with normal defaults; override any field via kwargs."""
    def _make(**overrides):
        data = dict(
            user_id="u1",
            endpoint="/items",
            method="GET",
            response_time=45.0,
            status_code=200,
            ip_address="10.0.0.1",
            payload_size=200,
        )
        data.update(overrides)
        return TrafficEvent(**data)
    return _make


@pytest.fixture
def fake_redis():
    """In-memory async Redis that mirrors the app's decode_responses=True client."""
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture
def patch_model(tmp_path, monkeypatch):
    """Point the Isolation Forest at a temp .pkl and reset module globals per test."""
    model_path = tmp_path / "isolation_forest.pkl"
    monkeypatch.setattr(anomaly, "MODEL_PATH", model_path)
    monkeypatch.setattr(anomaly, "_model", None)
    monkeypatch.setattr(anomaly, "_model_loaded", False)
    return model_path
