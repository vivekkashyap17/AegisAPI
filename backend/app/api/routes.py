from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from redis.asyncio import Redis
from typing import Optional
from datetime import datetime
import uuid

from app.core.db import get_db
from app.core.redis import get_redis
from app.core.dependencies import get_current_user
from app.models.traffic import TrafficEvent
from app.models.audit import AuditLog
from app.models.user import User
from app.services.scoring import calculate_risk_score
from app.services.trust import get_trust_score, update_trust_score, get_trust_action

router = APIRouter()


@router.post("/ingest")
async def ingest_traffic(
    event: TrafficEvent,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    risk = calculate_risk_score(event)

    trust_score = await update_trust_score(redis, event.user_id, risk["risk_score"])
    policy = await get_trust_action(trust_score, risk["risk_score"])

    audit_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=event.user_id,
        endpoint=event.endpoint,
        method=event.method,
        response_time=event.response_time,
        status_code=event.status_code,
        ip_address=event.ip_address,
        payload_size=event.payload_size or 0,
        risk_score=risk["risk_score"],
        risk_level=risk["risk_level"],
        action=policy["action"],
        reason=policy["reason"],
        timestamp=datetime.utcnow()
    )

    db.add(audit_entry)
    await db.flush()

    return {
        "request_id": str(audit_entry.id),
        "timestamp": audit_entry.timestamp.isoformat(),
        "status": "processed",
        "event": {
            "user_id": event.user_id,
            "endpoint": event.endpoint,
            "method": event.method,
            "ip_address": event.ip_address,
            "response_time": event.response_time,
            "status_code": event.status_code,
            "payload_size": event.payload_size
        },
        "analysis": {
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "trust_score": trust_score
        },
        "policy": {
            "action": policy["action"],
            "reason": policy["reason"]
        }
    }


@router.get("/trust/{user_id}")
async def get_user_trust(
    user_id: str,
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    score = await get_trust_score(redis, user_id)
    return {
        "user_id": user_id,
        "trust_score": score,
        "trust_level": "HIGH" if score >= 0.7 else "MEDIUM" if score >= 0.4 else "LOW"
    }


@router.get("/logs")
async def get_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
):
    filters = []
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action.upper())
    if risk_level:
        filters.append(AuditLog.risk_level == risk_level.upper())

    count_query = select(func.count()).select_from(AuditLog)
    if filters:
        count_query = count_query.where(*filters)
    total = (await db.execute(count_query)).scalar_one()

    query = select(AuditLog).order_by(desc(AuditLog.timestamp))
    if filters:
        query = query.where(*filters)
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "total": total,
        "count": len(logs),
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "id": str(log.id),
                "timestamp": log.timestamp.isoformat(),
                "user_id": log.user_id,
                "endpoint": log.endpoint,
                "method": log.method,
                "ip_address": log.ip_address,
                "response_time": log.response_time,
                "status_code": log.status_code,
                "payload_size": log.payload_size,
                "risk_score": log.risk_score,
                "risk_level": log.risk_level,
                "action": log.action,
                "reason": log.reason
            }
            for log in logs
        ]
    }


@router.get("/logs/{log_id}")
async def get_log_by_id(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        parsed_id = uuid.UUID(log_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid log ID format")

    result = await db.execute(
        select(AuditLog).where(AuditLog.id == parsed_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    return {
        "id": str(log.id),
        "timestamp": log.timestamp.isoformat(),
        "user_id": log.user_id,
        "endpoint": log.endpoint,
        "method": log.method,
        "ip_address": log.ip_address,
        "response_time": log.response_time,
        "status_code": log.status_code,
        "payload_size": log.payload_size,
        "risk_score": log.risk_score,
        "risk_level": log.risk_level,
        "action": log.action,
        "reason": log.reason
    }