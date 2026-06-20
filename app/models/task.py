from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import JSON
from sqlalchemy import DateTime

from datetime import datetime

from app.db.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    # Task Information
    type = Column(String)
    payload = Column(JSON)
    result = Column(JSON, nullable=True)

    # Task State
    status = Column(String, default="PENDING")

    # Priority
    priority = Column(String, default="MEDIUM")

    # Retry Information
    retries = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Scheduling
    scheduled_at = Column(DateTime, default=datetime.utcnow)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Error Tracking
    last_error = Column(String, nullable=True)