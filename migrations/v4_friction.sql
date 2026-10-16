-- Migration v4: Project Friction Analysis Layer Tables

CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(512) NOT NULL UNIQUE,
    default_branch VARCHAR(100) DEFAULT 'main',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS friction_analysis_runs (
    id VARCHAR(64) PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    workflow_id VARCHAR(64),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    time_window_days INTEGER DEFAULT 30,
    overall_friction_score FLOAT,
    friction_level VARCHAR(50),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS friction_raw_snapshots (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) REFERENCES friction_analysis_runs(id) ON DELETE CASCADE,
    entity_type VARCHAR(100) NOT NULL,
    external_id VARCHAR(255),
    snapshot_data JSONB,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS friction_metrics (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) REFERENCES friction_analysis_runs(id) ON DELETE CASCADE,
    metric_category VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    unit VARCHAR(50),
    details JSONB,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS friction_indicators (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) REFERENCES friction_analysis_runs(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    title VARCHAR(512) NOT NULL,
    summary TEXT NOT NULL,
    score_impact FLOAT DEFAULT 0.0,
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS friction_evidence (
    id SERIAL PRIMARY KEY,
    indicator_id INTEGER REFERENCES friction_indicators(id) ON DELETE CASCADE,
    run_id VARCHAR(64) REFERENCES friction_analysis_runs(id) ON DELETE CASCADE,
    entity_type VARCHAR(100),
    external_id VARCHAR(255),
    title VARCHAR(512),
    url TEXT,
    metrics_breakdown JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_repositories_full_name ON repositories(full_name);
CREATE INDEX IF NOT EXISTS ix_friction_runs_repository_id ON friction_analysis_runs(repository_id);
CREATE INDEX IF NOT EXISTS ix_friction_runs_workflow_id ON friction_analysis_runs(workflow_id);
CREATE INDEX IF NOT EXISTS ix_friction_runs_status ON friction_analysis_runs(status);
CREATE INDEX IF NOT EXISTS ix_friction_raw_snapshots_run_id ON friction_raw_snapshots(run_id);
CREATE INDEX IF NOT EXISTS ix_friction_raw_snapshots_entity_type ON friction_raw_snapshots(entity_type);
CREATE INDEX IF NOT EXISTS ix_friction_metrics_run_id ON friction_metrics(run_id);
CREATE INDEX IF NOT EXISTS ix_friction_indicators_run_id ON friction_indicators(run_id);
CREATE INDEX IF NOT EXISTS ix_friction_evidence_indicator_id ON friction_evidence(indicator_id);
CREATE INDEX IF NOT EXISTS ix_friction_evidence_run_id ON friction_evidence(run_id);
