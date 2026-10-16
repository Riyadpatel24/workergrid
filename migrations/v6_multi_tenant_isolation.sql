-- Migration v6: Strict Multi-Tenant Data Isolation & Scoped Indexes

-- 1. Ensure composite unique constraint on (user_id, full_name) for per-user repository ownership
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'repositories_full_name_key'
    ) THEN
        ALTER TABLE repositories DROP CONSTRAINT repositories_full_name_key;
    END IF;
END $$;

ALTER TABLE repositories DROP CONSTRAINT IF EXISTS uq_user_repository_full_name;
ALTER TABLE repositories ADD CONSTRAINT uq_user_repository_full_name UNIQUE (user_id, full_name);

-- 2. Verify all user_id indexes exist for fast tenant-scoped queries
CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS ix_repositories_user_id ON repositories(user_id);
CREATE INDEX IF NOT EXISTS ix_friction_runs_user_id ON friction_analysis_runs(user_id);
CREATE INDEX IF NOT EXISTS ix_friction_raw_snapshots_user_id ON friction_raw_snapshots(user_id);
CREATE INDEX IF NOT EXISTS ix_friction_metrics_user_id ON friction_metrics(user_id);
CREATE INDEX IF NOT EXISTS ix_friction_indicators_user_id ON friction_indicators(user_id);
CREATE INDEX IF NOT EXISTS ix_friction_evidence_user_id ON friction_evidence(user_id);
