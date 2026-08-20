from typing import Any
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: str = "MEDIUM"
    delay: int = Field(default=0, ge=0)
    required_capability: str | None = None
    max_retries: int = Field(default=3, ge=0, le=10)


class WorkflowTaskCreate(BaseModel):
    key: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: str = "MEDIUM"
    depends_on: list[str] = Field(default_factory=list)
    delay: int = Field(default=0, ge=0)
    required_capability: str | None = None
    max_retries: int = Field(default=3, ge=0, le=10)


class WorkflowCreate(BaseModel):
    name: str
    tasks: list[WorkflowTaskCreate] = Field(min_length=1)
