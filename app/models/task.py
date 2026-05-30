from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import JSON

from app.db.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    type = Column(String)

    status = Column(String)

    payload = Column(JSON)

    result = Column(JSON, nullable=True)