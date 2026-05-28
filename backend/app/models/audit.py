from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.core.db import Base
from datetime import datetime
import uuid


class AuditLog(Base):
    # -------------------------------------------------------
    # TABLE NAME
    # -------------------------------------------------------
    # SQLAlchemy maps this class to the "audit_logs" table
    # in PostgreSQL. If the table doesn't exist, init_db.py
    # will create it automatically.
    # -------------------------------------------------------
    __tablename__ = "audit_logs"

    # -------------------------------------------------------
    # PRIMARY KEY
    # -------------------------------------------------------
    # UUID instead of integer auto-increment because:
    # - UUIDs are globally unique across distributed systems
    # - Integer IDs leak information (tells attacker how many
    #   records exist, allows enumeration attacks)
    # - default=uuid.uuid4 generates a new UUID per record
    #   automatically — you never set this manually
    # -------------------------------------------------------
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # -------------------------------------------------------
    # TRAFFIC EVENT FIELDS
    # These mirror your TrafficEvent pydantic model exactly.
    # index=True on user_id and ip_address because you'll
    # frequently query "all events for user X" or
    # "all events from IP Y" — indexes make these fast.
    # -------------------------------------------------------
    user_id = Column(String(255), nullable=False, index=True)
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)       # GET, POST, etc.
    response_time = Column(Float, nullable=False)      # milliseconds
    status_code = Column(Integer, nullable=False)
    ip_address = Column(String(45), nullable=False, index=True)
    # String(45) covers both IPv4 (15 chars) and IPv6 (39 chars)
    payload_size = Column(Integer, default=0, nullable=False)

    # -------------------------------------------------------
    # RISK ANALYSIS FIELDS
    # Output from your scoring.py
    # -------------------------------------------------------
    risk_score = Column(Integer, nullable=False)
    risk_level = Column(String(10), nullable=False)    # LOW / MEDIUM / HIGH

    # -------------------------------------------------------
    # POLICY DECISION FIELDS
    # Output from your policy.py
    # -------------------------------------------------------
    action = Column(String(20), nullable=False)        # ALLOW / THROTTLE / BLOCK
    reason = Column(Text, nullable=False)              # Text instead of String
    # Text = unlimited length, String = fixed max length
    # Reason strings can be long in edge cases

    # -------------------------------------------------------
    # TIMESTAMP
    # -------------------------------------------------------
    # datetime.utcnow records when THIS record was saved
    # Always store UTC in database — convert to local time
    # only when displaying. Mixing timezones in storage
    # causes subtle bugs that are very hard to debug.
    # -------------------------------------------------------
    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True    # indexed because you'll query by time range frequently
    )

    def __repr__(self):
        # Clean string representation for debugging
        return (
            f"<AuditLog id={self.id} "
            f"user={self.user_id} "
            f"risk={self.risk_level} "
            f"action={self.action}>"
        )