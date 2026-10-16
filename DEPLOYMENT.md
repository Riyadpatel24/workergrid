# WorkerGrid + Project Friction Production Deployment Guide

## Architecture Overview

| Component | Service | Notes |
|---|---|---|
| Frontend (React/Vite) | Vercel | `frontend/` directory |
| FastAPI API | Render Web Service | `main.py` entry point |
| Background Worker | Render Background Worker | `worker.py` entry point |
| PostgreSQL | Render PostgreSQL | Managed, shared by API + Worker |
| Redis | Render Key Value | Managed, shared by API + Worker |

---

## Step 1 — Deploy Order

**Deploy in this order** (each step depends on outputs from the previous):
1. Render PostgreSQL (get DATABASE_URL)
2. Render Key Value/Redis (get REDIS_URL)
3. Render Web Service — workergrid-api (get backend URL)
4. Render Background Worker — workergrid-worker
5. GitHub OAuth App (needs backend URL for callback URL)
6. Vercel Frontend (needs backend URL for VITE_API_URL)

---

## Step 2 — Generate Production Secrets

Run these commands locally to generate stable secret values. Store them somewhere safe (password manager); you will paste them into the Render dashboard.

```bash
# SECRET_KEY (JWT signing key — HS256)
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY (Fernet key for encrypting stored GitHub tokens)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **IMPORTANT**: Generate these ONCE and store them permanently.  
> If `ENCRYPTION_KEY` changes, all stored GitHub tokens will become unreadable.  
> If `SECRET_KEY` changes, all existing JWT sessions will be invalidated.

---

## Step 3 — Render PostgreSQL

1. In the Render dashboard: **New → PostgreSQL**
2. Name it `workergrid-db`, choose the free plan, set region to `Oregon`
3. After provisioning, copy the **Internal Database URL** (starts with `postgresql://`)
4. Save it as `DATABASE_URL` in both `workergrid-api` and `workergrid-worker` environment variables

---

## Step 4 — Render Key Value (Redis)

1. In the Render dashboard: **New → Key Value**
2. Name it `workergrid-redis`, choose the free plan, set region to `Oregon`
3. After provisioning, copy the **Internal Redis URL** (starts with `redis://`)
4. Save it as `REDIS_URL` in both `workergrid-api` and `workergrid-worker` environment variables

---

## Step 5 — Database Migrations

The application creates all tables automatically via `Base.metadata.create_all` on API startup.
For a **fresh database**, that is sufficient for production.

If you are migrating an **existing** pre-v3 database, apply the additive SQL migrations in this order:

```bash
# Substitute your actual Render DB connection string
export PG_URL="postgresql://user:pass@host/db"

# v3: Add v3 worker/workflow columns to existing tasks table
psql "$PG_URL" -f migrations/v3.sql

# v4: Create Project Friction analysis tables
psql "$PG_URL" -f migrations/v4_friction.sql

# v5: Create users table and add user_id FK to all tables
psql "$PG_URL" -f migrations/v5_multi_user.sql

# v6: Enforce strict multi-tenant isolation constraints
psql "$PG_URL" -f migrations/v6_multi_tenant_isolation.sql
```

> These migrations are idempotent (`IF NOT EXISTS`, `IF EXISTS` guards).  
> Do NOT run them on a fresh database that was already created by `Base.metadata.create_all`.

---

## Step 6 — GitHub OAuth App Setup

1. Go to: **GitHub → Settings → Developer Settings → OAuth Apps → New OAuth App**
2. Set:
   - **Application name**: `WorkerGrid`
   - **Homepage URL**: `https://<your-vercel-frontend-url>`
   - **Authorization callback URL**: `https://workergrid-api.onrender.com/api/v1/auth/github/callback`
3. Click **Register Application**
4. Copy **Client ID** → set as `GITHUB_CLIENT_ID` in workergrid-api environment variables
5. Click **Generate a new client secret** → set as `GITHUB_CLIENT_SECRET` in workergrid-api
6. Set `GITHUB_REDIRECT_URI` to the exact callback URL from step 2

---

## Step 7 — Deploy to Render via Blueprint

The `render.yaml` in the repository root defines both services. In the Render dashboard:

1. **New → Blueprint**
2. Connect your GitHub repository (`Riyadpatel24/workergrid`)
3. Select the `workergrid-v2.0` branch
4. Render will detect `render.yaml` and create both services
5. For each `sync: false` environment variable, paste the values you generated above

---

## Step 8 — Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → Import from GitHub
2. Select repository `Riyadpatel24/workergrid`
3. Set **Root Directory** to `frontend`
4. Set **Framework Preset** to `Vite`
5. Add environment variable:
   - `VITE_API_URL` = `https://workergrid-api.onrender.com` (your Render API URL)
6. Deploy — Vercel will run `npm run build` and serve `dist/`

After deployment, copy the Vercel URL (e.g. `https://workergrid.vercel.app`) and set it in:
- `ALLOWED_ORIGINS` on `workergrid-api` (Render dashboard)
- Trigger a manual redeploy of `workergrid-api` so the new CORS origin takes effect

---

## Environment Variables Reference

### workergrid-api (Render Web Service)

| Variable | Source | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables `secure=True` cookies |
| `SECRET_KEY` | Generate | `secrets.token_hex(32)` |
| `ENCRYPTION_KEY` | Generate | `Fernet.generate_key().decode()` |
| `DATABASE_URL` | Render PostgreSQL | Internal URL |
| `REDIS_URL` | Render Key Value | Internal URL |
| `GITHUB_CLIENT_ID` | GitHub OAuth App | Public value |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App | **Secret** |
| `GITHUB_REDIRECT_URI` | Your backend URL | `https://workergrid-api.onrender.com/api/v1/auth/github/callback` |
| `GITHUB_OAUTH_SCOPES` | `repo,read:user` | Fixed value |
| `ALLOWED_ORIGINS` | Your Vercel URL | `https://workergrid.vercel.app` |
| `WORKER_CAPABILITIES` | `general,friction,github` | Fixed value |

### workergrid-worker (Render Background Worker)

| Variable | Source | Notes |
|---|---|---|
| `DATABASE_URL` | Same as API | Required |
| `REDIS_URL` | Same as API | Required |
| `SECRET_KEY` | Same as API | Required for token decryption |
| `ENCRYPTION_KEY` | Same as API | Required for GitHub token decryption |
| `WORKER_CAPABILITIES` | `general,friction,github` | Fixed value |
| `ENVIRONMENT` | `production` | |

### frontend (Vercel)

| Variable | Source | Notes |
|---|---|---|
| `VITE_API_URL` | Your Render API URL | e.g. `https://workergrid-api.onrender.com` |

---

## Health Check

```bash
curl https://workergrid-api.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "checks": { "database": "ok", "redis": "ok" },
  "timestamp": "..."
}
```

---

## Troubleshooting

- **Redis connection error**: Confirm `REDIS_URL` is the Internal URL (not External) — Internal URLs only work within Render's network.
- **Database migration errors**: Check if you're running migrations against a fresh vs. existing database. A fresh database created by `Base.metadata.create_all` already has all columns.
- **CORS errors in browser**: Verify `ALLOWED_ORIGINS` includes your exact Vercel origin (no trailing slash).
- **Cookie not sent cross-origin**: Confirm `credentials: "include"` is present in all fetch calls (already patched in this codebase).
- **GitHub OAuth callback mismatch**: The `GITHUB_REDIRECT_URI` environment variable must exactly match the callback URL registered in the GitHub OAuth App.
