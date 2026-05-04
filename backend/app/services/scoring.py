def calculate_risk_score(event):
    score = 0

    # High response time may indicate abuse / overload
    if event.response_time > 100:
        score += 30

    # Server errors can be suspicious
    if event.status_code >= 500:
        score += 25

    # Large payloads may indicate malicious requests
    if event.payload_size > 1000:
        score += 20

    # Sensitive endpoints
    if event.endpoint in ["/login", "/admin", "/payment"]:
        score += 15

    # Risk categories
    if score >= 60:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "risk_score": score,
        "risk_level": level
    }