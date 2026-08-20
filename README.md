# WorkerGrid v2.0 + v3.0

WorkerGrid is a distributed task-processing system built with FastAPI, Redis, PostgreSQL and Python workers.

## v2.0 completed scope

- Priority queues: HIGH / MEDIUM / LOW
- Delayed scheduling
- Worker registry and heartbeats
- Task-to-worker persistence
- Retries and Dead Letter Queue
- Recovery monitor
- Task listing and detailed execution history
- Client-oriented dashboard APIs
- CORS-enabled React integration

## v3.0 functional baseline

- Workflow DAGs with dependency validation
- Dependency-aware task release
- Worker capabilities
- Control-plane resource snapshot
- Scaling recommendations
- Manual task retry/cancel operations
- Improved autonomous recovery
- Expanded observability

The v3 control plane intentionally exposes **advisory scaling recommendations** rather than spawning local processes invisibly. Actual worker deployment/scaling remains an infrastructure concern (Docker/Kubernetes/cloud).

## Start

1. Start infrastructure:

```powershell
docker compose up -d
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. Apply the database migration once:

```powershell
docker exec -i workergrid_postgres psql -U workergrid -d workergrid < migrations/v3.sql
```

4. Start API:

```powershell
python -m uvicorn main:app --reload
```

5. Start scheduler, recovery monitor and one or more workers in separate terminals:

```powershell
python scheduler.py
python recovery_monitor.py
python worker.py
```

6. Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Important payload controls for demos

`duration` controls demo processing duration in seconds.

`fail: true` forces a failure and exercises retry/DLQ handling.

`crash: true` simulates a worker crash for recovery testing.

## API

- `GET /health`
- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{id}`
- `POST /tasks/{id}/retry`
- `POST /tasks/{id}/cancel`
- `GET /workers`
- `GET /stats`
- `GET /queues/priority`
- `GET /dashboard`
- `POST /workflows`
- `GET /workflows/{workflow_id}`
- `GET /control-plane`
