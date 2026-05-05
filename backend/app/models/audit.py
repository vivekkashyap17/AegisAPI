from sqlalchemy import Column, String, Float, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.db import Base
from datetime import datetime
import uuid


class AuditLog(Base):
    __tablename__ = "audit_logs"

    # Primary key — UUID is better than integer IDs for distributed systems
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Traffic event fields (mirrors your TrafficEvent pydantic model)
    user_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    method = Column(String, nullable=False)
    response_time = Column(Float, nullable=False)
    status_code = Column(Integer, nullable=False)
    ip_address = Column(String, nullable=False)
    payload_size = Column(Integer, default=0)

    # Risk analysis result
    risk_score = Column(Integer, nullable=False)
    risk_level = Column(String, nullable=False)  # LOW / MEDIUM / HIGH

    # Policy decision
    action = Column(String, nullable=False)       # ALLOW / THROTTLE / BLOCK
    reason = Column(String, nullable=False)

    # When this record was created
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)