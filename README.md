# WorkerGrid

A distributed task processing system built with **FastAPI, Redis, and PostgreSQL**.

WorkerGrid demonstrates how modern backend systems handle asynchronous jobs using a producer-consumer architecture with retries, dead letter queues, multiple workers, and monitoring APIs.

---

## ✨ Features

* Task creation API
* Background task processing
* Redis-based task queue
* PostgreSQL persistence
* Multiple worker support
* Automatic retry mechanism
* Dead Letter Queue (DLQ)
* Worker heartbeats
* Worker monitoring API
* System metrics API

---

## 🏗️ Architecture

```text
                FastAPI
                    |
        ----------------------
        |          |         |
        V          V         V
   POST /tasks  GET /tasks  GET /workers
                    |
              GET /stats
                    |
               Redis Queue
                    |
         -------------------
         |        |        |
         V        V        V
     Worker1 Worker2 Worker3
                    |
               PostgreSQL
```

---

## 🛠️ Tech Stack

### Backend

* FastAPI
* SQLAlchemy

### Database

* PostgreSQL

### Queue

* Redis

### Infrastructure

* Docker
* Docker Compose

### Language

* Python

---

## 📡 API Endpoints

### GET /

Checks whether WorkerGrid is running.

```http
GET /
```

---

### POST /tasks

Creates a background task.

```http
POST /tasks
```

Example:

```json
{
  "type": "demo",
  "payload": {
    "message": "hello"
  }
}
```

---

### GET /tasks/{task_id}

Returns task status and results.

```http
GET /tasks/{task_id}
```

---

### GET /workers

Returns active worker IDs and heartbeat timestamps.

```http
GET /workers
```

---

### GET /stats

Returns system metrics:

* Queued tasks
* Dead Letter Queue size
* Active workers
* Successful tasks
* Failed tasks

```http
GET /stats
```

---

## 🔄 Task Lifecycle

```text
PENDING
   |
   V
PROCESSING
   |
   V
SUCCESS
```

---

## ⚠️ Failure Flow

```text
PENDING
   |
   V
PROCESSING
   |
   V
RETRY
   |
   V
RETRY
   |
   V
FAILED
   |
   V
DEAD LETTER QUEUE
```

---

## 📁 Project Structure

```text
app/
├── api/
├── db/
├── models/
├── queue/
├── workers/
├── docker/
└── tests/

main.py
worker.py
```

---

## 🚀 Running WorkerGrid

### Start Redis and PostgreSQL

```bash
docker compose up
```

### Start the API

```bash
python -m uvicorn main:app --reload
```

### Start Workers

```bash
python worker.py
```

Run multiple worker instances for parallel task processing.

---

## 🛣️ Future Roadmap

### WorkerGrid v1.1

* Better monitoring
* Improved project structure
* Documentation improvements

### WorkerGrid v2

WorkerGrid will power future applications such as VoiceNotes by providing reusable distributed task processing infrastructure.

---

## 📊 Status

# WorkerGrid v1.0

**Core Features Complete**

* ✅ Task Queue
* ✅ Background Workers
* ✅ Multiple Workers
* ✅ Retries
* ✅ Dead Letter Queue
* ✅ Heartbeats
* ✅ Worker Monitoring
* ✅ System Metrics

---

Built as a backend systems engineering project to explore distributed task processing concepts.
