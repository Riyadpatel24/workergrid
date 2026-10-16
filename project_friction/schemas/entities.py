from datetime import datetime
from typing import Any
from pydantic import BaseModel


class RawPullRequestSnapshot(BaseModel):
    number: int
    title: str
    state: str
    user_login: str
    created_at: datetime
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    first_review_at: datetime | None = None
    review_comments_count: int = 0
    html_url: str
    raw_data: dict[str, Any] = {}


class RawWorkflowRunSnapshot(BaseModel):
    id: int
    name: str
    status: str
    conclusion: str | None = None
    created_at: datetime
    updated_at: datetime
    html_url: str
    raw_data: dict[str, Any] = {}


class RawIssueSnapshot(BaseModel):
    number: int
    title: str
    state: str
    created_at: datetime
    closed_at: datetime | None = None
    comments_count: int = 0
    html_url: str
    raw_data: dict[str, Any] = {}
