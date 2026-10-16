from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.core.time import utcnow_naive


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("user_id", "full_name", name="uq_user_repository_full_name"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(512), nullable=False, index=True)
    default_branch = Column(String(100), default="main")
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    user = relationship("User", back_populates="repositories")
    runs = relationship("FrictionAnalysisRun", back_populates="repository", cascade="all, delete-orphan")


class FrictionAnalysisRun(Base):
    __tablename__ = "friction_analysis_runs"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    time_window_days = Column(Integer, default=30)
    overall_friction_score = Column(Float, nullable=True)
    friction_level = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)
    error_message = Column(Text, nullable=True)

    user = relationship("User", back_populates="runs")
    repository = relationship("Repository", back_populates="runs")
    raw_snapshots = relationship("FrictionRawSnapshot", back_populates="run", cascade="all, delete-orphan")
    metrics = relationship("FrictionMetric", back_populates="run", cascade="all, delete-orphan")
    indicators = relationship("FrictionIndicator", back_populates="run", cascade="all, delete-orphan")
    evidence = relationship("FrictionEvidence", back_populates="run", cascade="all, delete-orphan")


class FrictionRawSnapshot(Base):
    __tablename__ = "friction_raw_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id = Column(String(64), ForeignKey("friction_analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    external_id = Column(String(255), nullable=True)
    snapshot_data = Column(JSON, nullable=True)
    fetched_at = Column(DateTime, default=utcnow_naive)

    run = relationship("FrictionAnalysisRun", back_populates="raw_snapshots")


class FrictionMetric(Base):
    __tablename__ = "friction_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id = Column(String(64), ForeignKey("friction_analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_category = Column(String(100), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    details = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, default=utcnow_naive)

    run = relationship("FrictionAnalysisRun", back_populates="metrics")


class FrictionIndicator(Base):
    __tablename__ = "friction_indicators"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id = Column(String(64), ForeignKey("friction_analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=False)
    score_impact = Column(Float, default=0.0)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)

    run = relationship("FrictionAnalysisRun", back_populates="indicators")
    evidence_items = relationship("FrictionEvidence", back_populates="indicator", cascade="all, delete-orphan")


class FrictionEvidence(Base):
    __tablename__ = "friction_evidence"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    indicator_id = Column(Integer, ForeignKey("friction_indicators.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id = Column(String(64), ForeignKey("friction_analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=True)
    external_id = Column(String(255), nullable=True)
    title = Column(String(512), nullable=True)
    url = Column(Text, nullable=True)
    metrics_breakdown = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)

    run = relationship("FrictionAnalysisRun", back_populates="evidence")
    indicator = relationship("FrictionIndicator", back_populates="evidence_items")

