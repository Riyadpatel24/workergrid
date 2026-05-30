from fastapi import FastAPI

from app.db.database import Base
from app.db.database import engine

from app.models.task import Task

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def root():
    return {
        "message": "WorkerGrid Running"
    }