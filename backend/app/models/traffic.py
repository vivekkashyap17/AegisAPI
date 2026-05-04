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
    timestamp: datetime
    payload_size: Optional[int] = 0