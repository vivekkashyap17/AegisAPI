from app.models.traffic import TrafficEvent

# Endpoints considered security-sensitive (mirrors scoring.py)
SENSITIVE_ENDPOINTS = {"/login", "/admin", "/payment"}

# Stable numeric encoding for HTTP methods; anything unknown maps to 4
METHOD_CODES = {"GET": 0, "POST": 1, "PUT": 2, "DELETE": 3}

# Order matters — the model is trained and queried on this exact layout
FEATURE_NAMES = [
    "response_time",
    "status_code",
    "payload_size",
    "is_sensitive_endpoint",
    "is_error",
    "method_code",
    "endpoint_length",
]

NUM_FEATURES = len(FEATURE_NAMES)


def extract_features(event: TrafficEvent) -> list[float]:
    """Turn a TrafficEvent into a fixed 7-dimensional numeric feature vector."""
    return [
        float(event.response_time),
        float(event.status_code),
        float(event.payload_size or 0),
        1.0 if event.endpoint in SENSITIVE_ENDPOINTS else 0.0,
        1.0 if event.status_code >= 400 else 0.0,
        float(METHOD_CODES.get(event.method.upper(), 4)),
        float(len(event.endpoint)),
    ]
