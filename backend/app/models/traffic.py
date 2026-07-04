from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TrafficEvent(BaseModel):
    user_id: str
    endpoint: str
    method: str
    response_time: float
    status_code: int
    ip_address: str
    timestamp: Optional[datetime] = None  # client-supplied, ignored for auditing (server uses receive time)
    payload_size: Optional[int] = 0