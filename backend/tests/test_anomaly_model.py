import random
import numpy as np

from app.services import anomaly
from app.services.features import extract_features


def _normal_vectors(make_event, n=100):
    random.seed(42)
    endpoints = ["/home", "/items", "/profile", "/search"]
    vecs = []
    for _ in range(n):
        e = make_event(
            endpoint=random.choice(endpoints),
            method=random.choice(["GET", "POST"]),
            response_time=random.uniform(20, 90),
            status_code=200,
            payload_size=random.randint(100, 600),
        )
        vecs.append(extract_features(e))
    return vecs


def _attack_vector(make_event):
    return np.array([extract_features(make_event(
        endpoint="/admin/" + "A" * 200, method="DELETE",
        response_time=9000, status_code=500, payload_size=9_000_000))], dtype=float)


def test_train_sets_model_and_writes_pkl(make_event, patch_model):
    anomaly._train_model(_normal_vectors(make_event))
    assert anomaly._model is not None
    assert patch_model.exists()


def test_attack_flagged_and_scored_higher_than_normal(make_event, patch_model):
    anomaly._train_model(_normal_vectors(make_event))

    normal = np.array([extract_features(make_event(response_time=50, payload_size=300))], dtype=float)
    attack = _attack_vector(make_event)

    assert int(anomaly._model.predict(attack)[0]) == -1  # -1 == anomaly
    normal_score = -float(anomaly._model.score_samples(normal)[0])
    attack_score = -float(anomaly._model.score_samples(attack)[0])
    assert attack_score > normal_score
