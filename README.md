# 🚀 WorkerGrid

> A distributed task processing system built with **FastAPI, Redis, PostgreSQL, and Docker**.

WorkerGrid explores how modern backend systems execute long-running tasks asynchronously using a producer-consumer architecture with background workers, retries, dead letter queues, and monitoring APIs.

---

# 🎯 Why WorkerGrid?

Many real-world applications need to perform expensive operations without blocking user requests.

Examples include:

* AI inference
* Email delivery
* Video processing
* File uploads
* Report generation
* Notifications
* Audio transcription

Instead of processing these tasks immediately, WorkerGrid demonstrates how they can be queued, processed in the background, retried automatically, and monitored.

---

# ✨ Features

## Task Processing

* Create background tasks
* Redis-backed task queue
* Asynchronous worker processing
* PostgreSQL persistence

## Reliability

* Automatic retries
* Dead Letter Queue (DLQ)
* Failure recovery
* Task state tracking

## Scalability

* Multiple worker processes
* Shared Redis queue
* Horizontal task distribution

## Monitoring

* Worker heartbeats
* Active worker monitoring
* System metrics API

---

# 🏗 Architecture

```text
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │
                           ▼
                  ┌────────────────┐
                  │     FastAPI    │
                  └──┬──────┬───┬──┘
                     │      │   │
              ┌──────┘      │   └──────┐
              ▼             ▼          ▼
          ┌───────┐   ┌─────────┐  ┌───────┐
          │ Tasks │   │ Workers │  │ Stats │
          └───┬───┘   └─────────┘  └───────┘
              │
              ▼
     ┌─────────────────┐
     │   Redis Queue   │
     └──┬──────┬───┬───┘
        │      │   │
        ▼      ▼   ▼
    ┌──────┐ ┌──────┐ ┌──────┐
    │  W1  │ │  W2  │ │  W3  │
    └──┬───┘ └──┬───┘ └──┬───┘
       └────────┼────────┘
                │
                ▼
       ┌──────────────────┐
       │    PostgreSQL    │
       └──────────────────┘
```

---

# 🔄 Task Lifecycle

```text
PENDING

↓

PROCESSING

↓

SUCCESS
```

---

# ⚠ Failure Flow

```text
PENDING

↓

PROCESSING

↓

RETRY

↓

RETRY

↓

FAILED

↓

DEAD LETTER QUEUE
```

# 🔁 Retry Strategy

WorkerGrid automatically retries failed tasks using **Exponential Retry Backoff**.

Retry Schedule

```text
Retry #1 → Wait 2 seconds

Retry #2 → Wait 4 seconds

Retry #3 → Move to Dead Letter Queue
```

This prevents retry storms and gives external services time to recover before another retry is attempted.

---

# 🛠 Tech Stack

| Component      | Technology |
| -------------- | ---------- |
| API            | FastAPI    |
| Database       | PostgreSQL |
| Queue          | Redis      |
| ORM            | SQLAlchemy |
| Infrastructure | Docker     |
| Language       | Python     |

---

# 📡 API Endpoints

| Endpoint        | Description     |
| --------------- | --------------- |
| GET /           | Health check    |
| POST /tasks     | Create a task   |
| GET /tasks/{id} | Get task status |
| GET /workers    | Active workers  |
| GET /stats      | System metrics  |

---

# 🚀 Example Workflow

## Create Task

```http
POST /tasks
```

```json
{
  "type": "demo",
  "payload": {
    "message": "hello"
  }
}
```

Response:

```json
{
  "task_id": 1,
  "status": "PENDING",
  "queued": true
}
```

---

## Processing Flow

```text
Client

↓

POST /tasks

↓

Redis Queue

↓

Background Worker

↓

PostgreSQL

↓

GET /tasks/{id}
```

---

# 📊 Monitoring

## Worker Monitoring

```http
GET /workers
```

Returns active workers and heartbeat timestamps.

## System Metrics

```http
GET /stats
```

Returns:

* Queued tasks
* Dead Letter Queue size
* Active workers
* Successful tasks
* Failed tasks

---

# 📁 Project Structure

```text
app/
├── api/
├── db/
├── models/
├── queue/
├── workers/

docker/
tests/

main.py
worker.py
```

---

# ⚡ Quick Start

## Start Redis and PostgreSQL

```bash
docker compose up
```

## Start FastAPI

```bash
python -m uvicorn main:app --reload
```

## Start Worker Processes

```bash
python worker.py
```

Run multiple worker instances for parallel task execution.

---

# 📈 Current Capabilities

## Core

* FastAPI
* PostgreSQL
* Redis
* Docker

## Processing

* Background workers
* Multiple workers
* Task queue

## Reliability

* Automatic retries
* Exponential Retry Backoff
* Dead Letter Queue (DLQ)
* Failure recovery
* Task state tracking

## Monitoring

* Worker heartbeats
* Worker monitoring API
* System metrics API

---

# 🛣 Future Roadmap

## WorkerGrid v1.1

Completed

- ✅ Priority Queue
- ✅ Delayed Tasks
- ✅ Exponential Retry Backoff

Planned

- Worker Registry
- Task Cancellation
- Enhanced Monitoring
- Dashboard

## WorkerGrid v2

WorkerGrid will serve as reusable infrastructure for future applications, including VoiceNotes, enabling distributed transcription and summarization pipelines.

---

# 📌 Status

## WorkerGrid v1.0

### ✅ Released

Completed features:

* Task Queue
* Background Workers
* Multiple Workers
* Automatic Retries
* Dead Letter Queue
* Worker Heartbeats
* Worker Monitoring API
* System Metrics API

---

# 👨‍💻 Project Goal

WorkerGrid was built to explore the backend engineering concepts behind modern distributed task processing systems.

The project focuses on asynchronous job execution, fault tolerance, worker coordination, and operational monitoring while providing a reusable foundation for future applications.

---

# 📚 Engineering Concepts Demonstrated

WorkerGrid explores several backend engineering concepts:

- Producer–Consumer Architecture
- Background Job Processing
- Redis-based Task Queues
- Asynchronous Processing
- Worker Processes
- Retry Mechanisms
- Exponential Retry Backoff
- Dead Letter Queue (DLQ)
- Worker Heartbeats
- Operational Monitoring


⭐ If you found this project interesting, consider giving it a star.
