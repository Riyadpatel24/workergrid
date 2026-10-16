from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.core.time import utcnow_naive


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    result = Column(JSON, nullable=True)

    status = Column(String, default="PENDING", index=True)
    priority = Column(String, default="MEDIUM", index=True)

    retries = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    scheduled_at = Column(DateTime, default=utcnow_naive, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    worker_id = Column(Integer, nullable=True, index=True)
    required_capability = Column(String, nullable=True, index=True)

    workflow_id = Column(String, nullable=True, index=True)
    workflow_key = Column(String, nullable=True)
    depends_on = Column(JSON, nullable=False, default=list)

    last_error = Column(String, nullable=True)

    user = relationship("User", back_populates="tasks")

