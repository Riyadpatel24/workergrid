# Upgrade from your current WorkerGrid v2.0 branch

Your uploaded project already had priority queues, scheduler, worker registry, metrics, CORS and task-to-worker tracking. This bundle keeps those ideas and extends them instead of introducing a second architecture.

## Before replacing files

1. Keep a copy of your current `workergrid` folder.
2. Keep your existing Git repository; this bundle intentionally does not contain `.git`.
3. Keep your existing PostgreSQL data.
4. Do not copy `venv`, `node_modules`, `.git`, `.env` or `__pycache__` into the project.

## Apply

Replace the project source with this bundle, then:

```powershell
# infrastructure
docker compose up -d

# backend
pip install -r requirements.txt

docker exec -i workergrid_postgres psql -U workergrid -d workergrid < migrations/v3.sql

# terminal 1
python -m uvicorn main:app --reload

# terminal 2
python scheduler.py

# terminal 3
python recovery_monitor.py

# terminal 4
python worker.py

# frontend
cd frontend
npm install
npm run lint
npm run dev
```

Open `http://localhost:5173`.

## First verification

Create a task with `examples/task.json` through Swagger `POST /tasks`.

Then watch the dashboard. The worker row should become BUSY and show `Task #<id>`. After completion, the task details should show the worker ID that executed it.

## v3 workflow verification

Use `examples/workflow.json` with `POST /workflows`.

The first task starts immediately. Later tasks remain WAITING until their dependencies report SUCCESS. `GET /workflows/{workflow_id}` shows the workflow lifecycle.

## Important v3 boundary

This bundle implements a functional control plane, workflow DAG execution, worker capabilities and resource/scaling recommendations. It deliberately does **not** silently spawn or kill operating-system processes or claim to be a Kubernetes autoscaler. Real multi-machine dynamic scaling belongs at the deployment/infrastructure layer.
