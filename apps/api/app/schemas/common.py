from datetime import time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

def _parse_time_value(value: object) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        parts = value.strip().split(":")
        if len(parts) == 2:
            hour, minute = int(parts[0]), int(parts[1])
            return time(hour, minute)
        if len(parts) == 3:
            hour, minute, second = int(parts[0]), int(parts[1]), int(parts[2])
            return time(hour, minute, second)
    raise ValueError("Invalid time; use HH:MM or HH:MM:SS")


TimeField = Annotated[time, BeforeValidator(_parse_time_value)]
class ReorderItem(BaseModel):
    id: UUID
    sort_order: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(default_factory=list)
class PaginatedResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int

