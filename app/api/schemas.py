from pydantic import BaseModel


class TaskCreate(BaseModel):
    type: str
    payload: dict