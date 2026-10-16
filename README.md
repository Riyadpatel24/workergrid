# WorkerGrid + Project Friction

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/Riyadpatel24/workergrid)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.0-61dafb.svg)](https://reactjs.org/)

**WorkerGrid** is a production-grade distributed task execution, workflow orchestration, and worker management engine.

**Project Friction** is a developer productivity and workflow analytics application built on top of WorkerGrid. It executes multi-stage DAG workflows to collect GitHub repository signals, calculate code review and CI/CD friction metrics, generate severity-classified indicators with evidence, and provide actionable engineering recommendations.

---

## Key Features

### WorkerGrid Core Platform
- **Multi-Tenant Task Processing**: Strict server-side user data isolation and ownership enforcement (`user_id`).
- **Priority-Based Dispatch**: Priority queues (`HIGH`, `MEDIUM`, `LOW`) with real-time Redis push/pop dispatching.
- **DAG Workflow Engine**: Multi-stage task dependency graphs with state persistence and automatic dependency release.
- **Capability Routing**: Automatic matching of task requirements (`general`, `friction`, `github`) to specialized worker pools.
- **Fault Tolerance & DLQ**: Automatic retries with exponential backoff delay and Dead-Letter Queue (DLQ) routing for exhausted tasks.
- **Scheduled Subsystem**: Time-based task activation for deferred and periodic execution.

### Project Friction Application
- **4-Stage DAG Workflow**:
  $$\text{friction\_init} \longrightarrow \text{friction\_collect\_github} \longrightarrow \text{friction\_calc\_metrics} \longrightarrow \text{friction\_generate\_report}$$
- **GitHub OAuth Integration**: Secure user-level OAuth 2.0 authorization with token encryption at rest.
- **Friction Scorecard**: Dimension scoring across Code Review, CI/CD, Backlog Staleness, and Delivery Velocity.
- **Evidence & Indicator Breakdown**: Severity-ranked indicators (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) linked directly to external GitHub PR, issue, and workflow run evidence.

---

## Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Uvicorn / Gunicorn
- **Database**: PostgreSQL (Production) / SQLite (Development & Testing)
- **Caching & Queuing**: Redis (Priority Queues, Worker Heartbeats, DLQ)
- **Security & OAuth**: Fernet Symmetric Token Encryption (`cryptography`), PyJWT, Bcrypt, HttpOnly Cookies
- **Frontend**: React 18, Vite, Lucide Icons, Vanilla CSS Design System

---

## Quickstart & Local Setup

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL & Redis (optional for unit testing, required for local live execution)

### 2. Backend Setup
```bash
# Clone repository
git clone https://github.com/Riyadpatel24/workergrid.git
cd workergrid

# Create & activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Run database migrations
psql -U workergrid -d workergrid -f migrations/v1_init.sql
psql -U workergrid -d workergrid -f migrations/v5_multi_user.sql
psql -U workergrid -d workergrid -f migrations/v6_multi_tenant_isolation.sql

# Start FastAPI API server
uvicorn main:app --reload --port 8000
```

### 3. Worker Setup
```bash
# Start worker process with capabilities
WORKER_CAPABILITIES=general,friction,github python worker.py
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to access the WorkerGrid platform and Project Friction application.

---

## Testing & Verification

```bash
# Run backend test suite (48 tests)
python -m unittest discover -s tests

# Run frontend linting & production build
cd frontend
npm run lint
npm run build
```

---

## License
Distributed under the MIT License.
