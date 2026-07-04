import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler
from redis.asyncio import Redis

from app.models.traffic import TrafficEvent
from app.services.features import extract_features

# Redis keys
BUFFER_KEY = "anomaly:buffer"   # capped list of the latest feature vectors
COUNT_KEY = "anomaly:count"     # total events ever seen (drives retrain cadence)

BUFFER_SIZE = 100               # need this many samples before the model is usable
RETRAIN_INTERVAL = 50           # retrain every N events once the buffer is full
CONTAMINATION = 0.05            # expected anomaly rate — controls the decision threshold

# Model is pickled next to this module so it survives restarts (gitignored)
MODEL_PATH = Path(__file__).parent / "isolation_forest.pkl"

_model: Optional[Pipeline] = None
_model_loaded = False           # whether we've attempted the one-time disk load


def _load_model_from_disk():
    """Lazily load a previously trained model so predictions survive restarts."""
    global _model, _model_loaded
    _model_loaded = True
    if MODEL_PATH.exists():
        try:
            with open(MODEL_PATH, "rb") as f:
                _model = pickle.load(f)
        except Exception:
            _model = None


def _train_model(vectors: list[list[float]]):
    """Fit a StandardScaler + Isolation Forest pipeline and persist it to disk.

    Scaling is required because the raw features live on wildly different scales
    (status_code ~200 vs endpoint_length ~5); without it the forest's score is
    dominated by the largest-magnitude features and flags normal traffic.
    """
    global _model
    X = np.array(vectors, dtype=float)
    model = make_pipeline(
        StandardScaler(),
        IsolationForest(
            n_estimators=100,
            contamination=CONTAMINATION,
            random_state=42,
        ),
    )
    model.fit(X)
    _model = model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)


async def analyze_event(redis: Redis, event: TrafficEvent) -> dict:
    """
    Score a single event for anomalousness.

    Accumulates feature vectors in a capped Redis buffer, (re)trains the
    Isolation Forest once enough data exists, and returns the verdict for
    the current event.
    """
    global _model
    if not _model_loaded:
        _load_model_from_disk()

    features = extract_features(event)

    # Append to the capped training buffer and count the event
    await redis.rpush(BUFFER_KEY, json.dumps(features))
    await redis.ltrim(BUFFER_KEY, -BUFFER_SIZE, -1)
    count = await redis.incr(COUNT_KEY)
    buffer_len = await redis.llen(BUFFER_KEY)

    # Train once we first have a full buffer, then periodically thereafter
    should_train = buffer_len >= BUFFER_SIZE and (
        _model is None or count % RETRAIN_INTERVAL == 0
    )
    if should_train:
        raw = await redis.lrange(BUFFER_KEY, 0, -1)
        vectors = [json.loads(v) for v in raw]
        _train_model(vectors)

    if _model is None:
        return {
            "anomaly_detected": False,
            "anomaly_score": 0.0,
            "model_ready": False,
        }

    X = np.array([features], dtype=float)
    prediction = int(_model.predict(X)[0])        # -1 = anomaly, 1 = normal
    raw_score = float(_model.score_samples(X)[0])  # lower = more anomalous
    return {
        "anomaly_detected": prediction == -1,
        "anomaly_score": round(-raw_score, 4),     # flip so higher = more anomalous
        "model_ready": True,
    }
