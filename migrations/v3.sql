-- Run once against the existing WorkerGrid database before starting v3.
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS worker_id INTEGER;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS required_capability VARCHAR;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS workflow_id VARCHAR;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS workflow_key VARCHAR;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS depends_on JSON;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 3;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS last_error VARCHAR;
CREATE INDEX IF NOT EXISTS ix_tasks_worker_id ON tasks(worker_id);
CREATE INDEX IF NOT EXISTS ix_tasks_workflow_id ON tasks(workflow_id);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS ix_tasks_created_at ON tasks(created_at);
UPDATE tasks SET depends_on = '[]'::json WHERE depends_on IS NULL;
UPDATE tasks SET max_retries = 3 WHERE max_retries IS NULL;
