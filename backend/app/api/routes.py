from fastapi import APIRouter
from app.models.traffic import TrafficEvent
from app.services.scoring import calculate_risk_score
from app.services.policy import apply_policy

router = APIRouter()


@router.post("/ingest")
def ingest_traffic(event: TrafficEvent):
    risk = calculate_risk_score(event)
    policy = apply_policy(risk)

    return {
        "message": "Traffic event processed",
        "data": event.dict(),
        "analysis": risk,
        "policy": policy
    }