from dataclasses import dataclass
from datetime import datetime

from .enums import Channel, CommType


@dataclass
class Communication:
    comm_id: str
    client_pin: int
    comm_date: datetime
    comm_type: CommType
    channel: Channel
    offer_id: str
    success: int
