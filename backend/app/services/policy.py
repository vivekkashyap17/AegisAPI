def apply_policy(risk_analysis):
    score = risk_analysis["risk_score"]

    if score >= 60:
        action = "BLOCK"
        reason = "High-risk traffic detected"
    elif score >= 30:
        action = "THROTTLE"
        reason = "Moderate-risk traffic, limiting access"
    else:
        action = "ALLOW"
        reason = "Normal traffic"

    return {
        "action": action,
        "reason": reason
    }