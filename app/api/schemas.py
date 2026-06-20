from pydantic import BaseModel


class TaskCreate(BaseModel):
    type: str

    payload: dict

    priority: str = "MEDIUM"

    delay: int = 0