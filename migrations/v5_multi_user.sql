-- Migration v5: Multi-Tenant Users & Ownership Foreign Keys

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255),
    full_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

CREATE TABLE IF NOT EXISTS user_github_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    github_user_id BIGINT,
    github_username VARCHAR(255),
    encrypted_access_token TEXT,
    scopes VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_user_github_accounts_user_id ON user_github_accounts(user_id);
CREATE INDEX IF NOT EXISTS ix_user_github_accounts_github_user_id ON user_github_accounts(github_user_id);

-- Add user_id to tasks (nullable for legacy/unowned tasks)
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks(user_id);

-- Add user_id to repositories and update unique constraint
ALTER TABLE repositories ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE repositories DROP CONSTRAINT IF EXISTS repositories_full_name_key;
ALTER TABLE repositories ADD CONSTRAINT uq_user_repository_full_name UNIQUE (user_id, full_name);
CREATE INDEX IF NOT EXISTS ix_repositories_user_id ON repositories(user_id);

-- Add user_id to friction analysis runs and child tables (nullable for legacy runs)
ALTER TABLE friction_analysis_runs ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_friction_runs_user_id ON friction_analysis_runs(user_id);

ALTER TABLE friction_raw_snapshots ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_friction_raw_snapshots_user_id ON friction_raw_snapshots(user_id);

ALTER TABLE friction_metrics ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_friction_metrics_user_id ON friction_metrics(user_id);

ALTER TABLE friction_indicators ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_friction_indicators_user_id ON friction_indicators(user_id);

ALTER TABLE friction_evidence ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_friction_evidence_user_id ON friction_evidence(user_id);
