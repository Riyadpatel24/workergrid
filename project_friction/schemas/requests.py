from pydantic import BaseModel, Field


class StartAnalysisRequest(BaseModel):
    owner: str = Field(..., example="facebook")
    name: str = Field(..., example="react")
    time_window_days: int = Field(default=30, ge=1, le=180)
    github_token: str | None = Field(default=None, description="Optional GitHub Personal Access Token for higher rate limits")
