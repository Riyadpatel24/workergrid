import {
  Activity,
  AlertTriangle, CheckCircle2,
  ChevronRight,
  Clock,
  Database,
  Inbox,
  Layers,
  Radio,
  RefreshCw, Search,
  Server,
  Settings2,
  Wifi, WifiOff,
  XCircle
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

/* ============================================================================
   WORKERGRID OPERATIONS CONSOLE
   Frontend-only. Reads from the existing FastAPI backend. Never mutates
   backend logic, models, or Redis/queue behavior. No fabricated data —
   any metric the current API does not yet expose is shown as a pending
   slot, not a fake number.
   ============================================================================ */

/* ----------------------------------------------------------------------------
   1. API SERVICE LAYER
   All network access is isolated here. UI components never call fetch()
   directly. To wire up a new backend endpoint (e.g. the Issue #10 priority
   queue endpoint), add one entry to ENDPOINTS and one method to `api`.
---------------------------------------------------------------------------- */

const ENDPOINTS = {
  root: "/",
  task: (id) => `/tasks/${id}`,
  workers: "/workers",
  stats: "/stats",
  dashboard: "/dashboard",
  // --- Reserved for Issue #10 (Priority Queue Manager). Not implemented
  // backend-side yet. Wire this up the moment the endpoint ships; every
  // component below already knows how to render a "pending" state until
  // real data lands here.
  queues: "/queues/priority",
};

function buildUrl(baseUrl, path) {
  if (!baseUrl) return path;
  return baseUrl.replace(/\/+$/, "") + path;
}

async function request(baseUrl, path, { signal } = {}) {
  const url = buildUrl(baseUrl, path);
  const res = await fetch(url, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    const err = new Error(`${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

const api = {
  getRoot: (baseUrl, opts) => request(baseUrl, ENDPOINTS.root, opts),
  getWorkers: (baseUrl, opts) => request(baseUrl, ENDPOINTS.workers, opts),
  getStats: (baseUrl, opts) => request(baseUrl, ENDPOINTS.stats, opts),
  getDashboard: (baseUrl, opts) => request(baseUrl, ENDPOINTS.dashboard, opts),
  getTask: (baseUrl, id, opts) => request(baseUrl, ENDPOINTS.task(id), opts),
  // Future: priority queue depths (Issue #10). Fails soft — callers treat
  // a thrown error here as "endpoint not deployed yet", not a system fault.
  getQueues: (baseUrl, opts) => request(baseUrl, ENDPOINTS.queues, opts),
};

/* ----------------------------------------------------------------------------
   2. DATA HOOKS
   Polling + state, decoupled from rendering.
---------------------------------------------------------------------------- */

function usePoll(fn, intervalMs, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const controllerRef = useRef(null);

  const run = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      const result = await fn({ signal: controller.signal });
      setData(result);
      setError(null);
      setUpdatedAt(new Date());
    } catch (e) {
      if (e.name !== "AbortError") setError(e);
    } finally {
      setLoading(false);
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    run();
    if (!intervalMs) return;
    const id = setInterval(run, intervalMs);
    return () => {
      clearInterval(id);
      controllerRef.current?.abort();
    };
  }, [run, intervalMs]);

  return { data, error, loading, updatedAt, refetch: run };
}

function useWorkerGridData(baseUrl) {
  const health = usePoll((o) => api.getRoot(baseUrl, o), 15000, [baseUrl]);
  const workers = usePoll((o) => api.getWorkers(baseUrl, o), 5000, [baseUrl]);
  const stats = usePoll((o) => api.getStats(baseUrl, o), 8000, [baseUrl]);
  const dashboard = usePoll((o) => api.getDashboard(baseUrl, o), 10000, [baseUrl]);
  const queues = usePoll((o) => api.getQueues(baseUrl, o), 5000, [baseUrl]);
  return { health, workers, stats, dashboard, queues };
}

/* ----------------------------------------------------------------------------
   3. DERIVED / ALERT LOGIC
   Alerts are computed client-side from real polled data only.
---------------------------------------------------------------------------- */

function computeAlerts({ health, workers, stats, queues }) {
  const alerts = [];

  if (health.error) {
    alerts.push({ level: "critical", text: "Cannot reach API root — backend may be down.", source: "GET /" });
  }
  if (workers.error) {
    alerts.push({ level: "warning", text: "Worker registry unavailable.", source: "GET /workers" });
  }
  if (stats.error) {
    alerts.push({ level: "warning", text: "Stats endpoint unavailable.", source: "GET /stats" });
  }

  const workerList = Array.isArray(workers.data) ? workers.data
    : Array.isArray(workers.data?.workers) ? workers.data.workers : [];

  const offline = workerList.filter((w) => classifyWorker(w) === "offline");
  if (offline.length > 0) {
    alerts.push({
      level: "critical",
      text: `${offline.length} worker${offline.length > 1 ? "s" : ""} offline / missed heartbeat.`,
      source: "GET /workers",
    });
  }

  const s = stats.data || {};
  const dlqCount = numOrNull(s.dlq_count ?? s.dead_letter_count ?? s.dlq);
  if (dlqCount !== null && dlqCount > 0) {
    alerts.push({
      level: "warning",
      text: `${dlqCount} task${dlqCount > 1 ? "s" : ""} in the Dead Letter Queue.`,
      source: "GET /stats",
    });
  }

  const failed = numOrNull(s.failed_tasks ?? s.failed);
  const successful = numOrNull(s.successful_tasks ?? s.successful);
  if (failed !== null && successful !== null && failed + successful > 0) {
    const rate = failed / (failed + successful);
    if (rate > 0.2) {
      alerts.push({
        level: "critical",
        text: `Failure rate at ${(rate * 100).toFixed(1)}% of completed tasks.`,
        source: "GET /stats",
      });
    }
  }

  if (queues.error) {
    alerts.push({
      level: "info",
      text: "Priority queue endpoint (Issue #10) not yet deployed — HIGH/MEDIUM/LOW depths pending.",
      source: "GET /queues/priority",
    });
  }

  return alerts;
}

function numOrNull(v) {
  return typeof v === "number" && !Number.isNaN(v) ? v : null;
}

function classifyWorker(w) {
  const rawStatus = String(w.status || "").toUpperCase();
  if (rawStatus === "OFFLINE" || rawStatus === "DOWN" || rawStatus === "DEAD") return "offline";
  if (w.current_task || rawStatus === "BUSY") return "busy";
  if (rawStatus === "ONLINE" || rawStatus === "IDLE" || rawStatus === "READY") return "online";
  // fall back to heartbeat staleness if provided
  if (w.last_heartbeat) {
    const age = Date.now() - new Date(w.last_heartbeat).getTime();
    if (age > 60000) return "offline";
  }
  return "online";
}

/* ----------------------------------------------------------------------------
   4. PRESENTATION PRIMITIVES
---------------------------------------------------------------------------- */

const STATUS_META = {
  online: { label: "ONLINE", color: "var(--c-online)" },
  busy: { label: "BUSY", color: "var(--c-busy)" },
  offline: { label: "OFFLINE", color: "var(--c-critical)" },
};

function Badge({ tone = "muted", children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function Panel({ title, icon: Icon, right, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head">
        <div className="panel-title">
          {Icon && <Icon size={14} strokeWidth={2} />}
          <span>{title}</span>
        </div>
        {right}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function EmptyState({ label }) {
  return <div className="empty-state">{label}</div>;
}

function timeAgo(date) {
  if (!date) return "—";
  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 2) return "just now";
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
}

/* ----------------------------------------------------------------------------
   5. SIGNATURE ELEMENT — GRID PULSE
   A schematic of the real pipeline (FastAPI → Scheduler → priority queues
   → Worker Pool → PostgreSQL). Pulse density along each queue lane reflects
   real queue depth when the Issue #10 endpoint is live; otherwise lanes sit
   idle with a single tracer so the topology still reads correctly.
---------------------------------------------------------------------------- */

function GridPulse({ queueDepths, workerBusyCount, dlqCount }) {
  const lanes = [
    { key: "high", label: "HIGH", y: 40, color: "var(--c-high)" },
    { key: "medium", label: "MEDIUM", y: 90, color: "var(--c-medium)" },
    { key: "low", label: "LOW", y: 140, color: "var(--c-low)" },
  ];

  return (
    <div className="gridpulse-wrap">
      <svg viewBox="0 0 720 200" className="gridpulse-svg" role="img" aria-label="Task flow topology">
        {/* lane rails */}
        <text x="8" y="24" className="gp-node-label">FASTAPI</text>
        <rect x="4" y="34" width="86" height="132" rx="3" className="gp-node-box" />
        <text x="47" y="104" textAnchor="middle" className="gp-node-sub">scheduler.py</text>
        <text x="47" y="120" textAnchor="middle" className="gp-node-sub-dim">SCHEDULED → PENDING</text>

        {lanes.map((lane, i) => {
          const depth = queueDepths?.[lane.key];
          const known = typeof depth === "number";
          return (
            <g key={lane.key}>
              <line x1="90" y1={lane.y} x2="520" y2={lane.y} className="gp-lane" style={{ stroke: lane.color }} />
              <text x="96" y={lane.y - 8} className="gp-lane-label" style={{ fill: lane.color }}>
                {lane.label}_PRIORITY_QUEUE
              </text>
              <text x="514" y={lane.y - 8} textAnchor="end" className="gp-lane-count">
                {known ? depth : "···"}
              </text>
              {/* tracer pulse */}
              <circle r="3.2" className="gp-pulse" style={{ fill: lane.color }}>
                <animateMotion
                  dur={known ? `${Math.max(1.1, 2.6 - depth * 0.12)}s` : "3.2s"}
                  repeatCount="indefinite"
                  path={`M90,${lane.y} L520,${lane.y}`}
                  begin={`${i * 0.4}s`}
                />
              </circle>
            </g>
          );
        })}

        <rect x="524" y="34" width="96" height="132" rx="3" className="gp-node-box" />
        <text x="572" y="24" textAnchor="middle" className="gp-node-label">WORKER POOL</text>
        <text x="572" y="104" textAnchor="middle" className="gp-node-sub">
          {typeof workerBusyCount === "number" ? `${workerBusyCount} busy` : "···"}
        </text>
        <text x="572" y="120" textAnchor="middle" className="gp-node-sub-dim">HIGH → MED → LOW</text>

        <line x1="620" y1="100" x2="672" y2="100" className="gp-lane" style={{ stroke: "var(--c-border-bright)" }} />
        <circle r="3.2" className="gp-pulse" style={{ fill: "var(--c-text-dim)" }}>
          <animateMotion dur="1.4s" repeatCount="indefinite" path="M620,100 L672,100" />
        </circle>
        <text x="676" y="24" className="gp-node-label">POSTGRES</text>
        <rect x="676" y="34" width="40" height="132" rx="3" className="gp-node-box" />
        <Database x="686" y="90" width="20" height="20" color="var(--c-text-dim)" />

        {/* DLQ branch */}
        <line x1="572" y1="166" x2="572" y2="192" className="gp-lane-dlq" />
        <text x="572" y="199" textAnchor="middle" className="gp-dlq-label">
          DLQ {typeof dlqCount === "number" ? `· ${dlqCount}` : ""}
        </text>
      </svg>
    </div>
  );
}

/* ----------------------------------------------------------------------------
   6. CONNECTION / TOP BAR
---------------------------------------------------------------------------- */

function ConnectionBar({ baseUrl, setBaseUrl, health, onRefreshAll }) {
  const [draft, setDraft] = useState(baseUrl);
  const isUp = !health.error && !!health.data;
  const isLoading = health.loading;

  return (
    <div className="connbar">
      <div className="brand">
        <Layers size={18} strokeWidth={2.2} />
        <span className="brand-name">WORKERGRID</span>
        <span className="brand-sub">OPERATIONS CONSOLE</span>
      </div>

      <div className="conn-status">
        <span className={`pulse-dot ${isLoading ? "dim" : isUp ? "up" : "down"}`} />
        {isLoading ? (
          <span className="conn-text">CONNECTING…</span>
        ) : isUp ? (
          <span className="conn-text up">
            <Wifi size={13} /> HEALTHY
          </span>
        ) : (
          <span className="conn-text down">
            <WifiOff size={13} /> UNREACHABLE
          </span>
        )}
      </div>

      <div className="conn-controls">
        <Settings2 size={13} className="conn-icon" />
        <input
          className="conn-input"
          placeholder="API base URL (blank = same origin)"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => setBaseUrl(draft.trim())}
          onKeyDown={(e) => e.key === "Enter" && setBaseUrl(draft.trim())}
          spellCheck={false}
        />
        <span className="conn-updated">synced {timeAgo(health.updatedAt)}</span>
        <button className="icon-btn" onClick={onRefreshAll} title="Refresh all">
          <RefreshCw size={14} />
        </button>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
   7. SYSTEM HEALTH STRIP
---------------------------------------------------------------------------- */

function SystemHealthStrip({ health, workers, stats }) {
  const workerList = Array.isArray(workers.data) ? workers.data
    : Array.isArray(workers.data?.workers) ? workers.data.workers : [];
  const offlineCount = workerList.filter((w) => classifyWorker(w) === "offline").length;
  const overall = health.error || offlineCount > 0 ? (health.error ? "critical" : "warning") : "healthy";

  const items = [
    {
      label: "SYSTEM",
      value: overall === "healthy" ? "HEALTHY" : overall === "warning" ? "WARNING" : "CRITICAL",
      tone: overall,
      icon: overall === "healthy" ? CheckCircle2 : overall === "warning" ? AlertTriangle : XCircle,
    },
    { label: "WORKERS REGISTERED", value: workerList.length || (workers.loading ? "···" : "0"), tone: "neutral", icon: Server },
    {
      label: "WORKERS OFFLINE",
      value: workers.loading ? "···" : String(offlineCount),
      tone: offlineCount > 0 ? "critical" : "neutral",
      icon: XCircle,
    },
    {
      label: "AVG PROCESSING TIME",
      value: fmtDuration(numOrNull(stats.data?.average_processing_time ?? stats.data?.avg_processing_time)),
      tone: "neutral",
      icon: Clock,
    },
  ];

  return (
    <div className="health-strip">
      {items.map((it) => (
        <div key={it.label} className={`health-chip tone-${it.tone}`}>
          <it.icon size={14} />
          <div>
            <div className="health-chip-value">{it.value}</div>
            <div className="health-chip-label">{it.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function fmtDuration(seconds) {
  if (seconds === null) return "···";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

/* ----------------------------------------------------------------------------
   8. WORKER MONITORING TABLE
---------------------------------------------------------------------------- */

function WorkerTable({ workers }) {
  const list = Array.isArray(workers.data) ? workers.data
    : Array.isArray(workers.data?.workers) ? workers.data.workers : [];

  return (
    <Panel
      title="WORKER MONITORING"
      icon={Server}
      right={<span className="panel-count">{list.length}</span>}
    >
      {workers.error ? (
        <EmptyState label="Worker registry unreachable — GET /workers failed." />
      ) : workers.loading && list.length === 0 ? (
        <EmptyState label="Loading workers…" />
      ) : list.length === 0 ? (
        <EmptyState label="No workers currently registered." />
      ) : (
        <div className="table-scroll">
          <table className="grid-table">
            <thead>
              <tr>
                <th>WORKER ID</th>
                <th>HOSTNAME</th>
                <th>STATUS</th>
                <th>CURRENT TASK</th>
                <th>COMPLETED</th>
                <th>FAILED</th>
                <th>VERSION</th>
              </tr>
            </thead>
            <tbody>
              {list.map((w, i) => {
                const cls = classifyWorker(w);
                const meta = STATUS_META[cls];
                return (
                  <tr key={w.worker_id ?? w.id ?? i}>
                    <td className="mono">{w.worker_id ?? w.id ?? "—"}</td>
                    <td className="mono">{w.hostname ?? "—"}</td>
                    <td>
                      <span className="status-pill" style={{ "--dot": meta.color }}>
                        <span className="status-dot" />
                        {meta.label}
                      </span>
                    </td>
                    <td className="mono dim">{w.current_task ?? "idle"}</td>
                    <td className="mono">{w.completed_tasks ?? w.completed ?? "—"}</td>
                    <td className={`mono ${(w.failed_tasks ?? w.failed) > 0 ? "num-bad" : ""}`}>
                      {w.failed_tasks ?? w.failed ?? "—"}
                    </td>
                    <td className="mono dim">{w.version ?? w.worker_version ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

/* ----------------------------------------------------------------------------
   9. QUEUE MONITORING
---------------------------------------------------------------------------- */

function QueueMonitor({ queues, stats }) {
  const known = !queues.error && queues.data;
  const depths = known
    ? {
        high: numOrNull(queues.data.high ?? queues.data.high_priority_queue),
        medium: numOrNull(queues.data.medium ?? queues.data.medium_priority_queue),
        low: numOrNull(queues.data.low ?? queues.data.low_priority_queue),
      }
    : {};
  const dlq = numOrNull(
    queues.data?.dlq ?? stats.data?.dlq_count ?? stats.data?.dead_letter_count
  );

  const cards = [
    { key: "high", label: "HIGH_PRIORITY_QUEUE", value: depths.high, color: "var(--c-high)" },
    { key: "medium", label: "MEDIUM_PRIORITY_QUEUE", value: depths.medium, color: "var(--c-medium)" },
    { key: "low", label: "LOW_PRIORITY_QUEUE", value: depths.low, color: "var(--c-low)" },
    { key: "dlq", label: "DEAD_LETTER_QUEUE", value: dlq, color: "var(--c-critical)" },
  ];

  const maxVal = Math.max(1, ...cards.map((c) => c.value || 0));

  return (
    <Panel
      title="QUEUE MONITORING"
      icon={Inbox}
      right={!known && <Badge tone="pending">ISSUE #10 · PENDING</Badge>}
    >
      <div className="queue-grid">
        {cards.map((c) => (
          <div key={c.key} className="queue-card">
            <div className="queue-card-top">
              <span className="queue-card-label" style={{ color: c.color }}>{c.label}</span>
              <span className="mono queue-card-value">
                {c.value === null || c.value === undefined ? "···" : c.value}
              </span>
            </div>
            <div className="queue-bar-track">
              <div
                className="queue-bar-fill"
                style={{
                  width: c.value ? `${Math.min(100, (c.value / maxVal) * 100)}%` : "3%",
                  background: c.color,
                  opacity: c.value === null || c.value === undefined ? 0.25 : 1,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      {!known && (
        <div className="queue-pending-note">
          Waiting on the priority queue endpoint (Issue #10). This panel renders live the
          moment <code className="mono">GET /queues/priority</code> ships.
        </div>
      )}
    </Panel>
  );
}

/* ----------------------------------------------------------------------------
   10. TASK STATISTICS
---------------------------------------------------------------------------- */

function TaskStatistics({ stats }) {
  const s = stats.data || {};
  const items = [
    { label: "PENDING", value: s.pending_tasks ?? s.pending, tone: "neutral" },
    { label: "PROCESSING", value: s.processing_tasks ?? s.processing, tone: "busy" },
    { label: "SCHEDULED", value: s.scheduled_tasks ?? s.scheduled, tone: "neutral" },
    { label: "SUCCESSFUL", value: s.successful_tasks ?? s.successful, tone: "online" },
    { label: "FAILED", value: s.failed_tasks ?? s.failed, tone: "critical" },
    {
      label: "AVG PROCESSING TIME",
      value: fmtDuration(numOrNull(s.average_processing_time ?? s.avg_processing_time)),
      tone: "neutral",
      raw: true,
    },
  ];

  return (
    <Panel title="TASK STATISTICS" icon={Activity}>
      {stats.error ? (
        <EmptyState label="Stats endpoint unreachable — GET /stats failed." />
      ) : (
        <div className="stat-grid">
          {items.map((it) => (
            <div key={it.label} className={`stat-cell tone-${it.tone}`}>
              <div className="stat-value mono">
                {it.raw ? it.value : (it.value ?? (stats.loading ? "···" : "—"))}
              </div>
              <div className="stat-label">{it.label}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/* ----------------------------------------------------------------------------
   11. ALERTS
---------------------------------------------------------------------------- */

function AlertsPanel({ alerts }) {
  return (
    <Panel title="ALERTS" icon={AlertTriangle} right={<span className="panel-count">{alerts.length}</span>}>
      {alerts.length === 0 ? (
        <EmptyState label="No active alerts." />
      ) : (
        <ul className="alert-list">
          {alerts.map((a, i) => (
            <li key={i} className={`alert-row tone-${a.level}`}>
              <span className="alert-dot" />
              <div className="alert-body">
                <div className="alert-text">{a.text}</div>
                <div className="alert-source mono">{a.source}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/* ----------------------------------------------------------------------------
   12. TASK LOOKUP (GET /tasks/{task_id})
---------------------------------------------------------------------------- */

function TaskLookup({ baseUrl }) {
  const [taskId, setTaskId] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const lookup = async () => {
    if (!taskId.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.getTask(baseUrl, taskId.trim());
      setResult(data);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel title="TASK LOOKUP" icon={Search} className="task-lookup">
      <div className="lookup-row">
        <input
          className="conn-input lookup-input"
          placeholder="task_id"
          value={taskId}
          onChange={(e) => setTaskId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && lookup()}
          spellCheck={false}
        />
        <button className="icon-btn" onClick={lookup} title="Look up task">
          <ChevronRight size={14} />
        </button>
      </div>
      {loading && <div className="lookup-status">querying…</div>}
      {error && <div className="lookup-status bad">GET /tasks/{taskId} → {error.message}</div>}
      {result && (
        <pre className="lookup-result mono">{JSON.stringify(result, null, 2)}</pre>
      )}
    </Panel>
  );
}

/* ----------------------------------------------------------------------------
   13. ROOT APP
---------------------------------------------------------------------------- */

export default function App() {
  const [baseUrl, setBaseUrl] = useState("");
  const { health, workers, stats, dashboard, queues } = useWorkerGridData(baseUrl);

  const alerts = computeAlerts({ health, workers, stats, queues });

  const workerList = Array.isArray(workers.data) ? workers.data
    : Array.isArray(workers.data?.workers) ? workers.data.workers : [];
  const busyCount = workerList.filter((w) => classifyWorker(w) === "busy").length;

  const queueDepths = !queues.error && queues.data
    ? {
        high: numOrNull(queues.data.high ?? queues.data.high_priority_queue),
        medium: numOrNull(queues.data.medium ?? queues.data.medium_priority_queue),
        low: numOrNull(queues.data.low ?? queues.data.low_priority_queue),
      }
    : {};
  const dlqCount = numOrNull(
    queues.data?.dlq ?? stats.data?.dlq_count ?? stats.data?.dead_letter_count
  );

  const refreshAll = () => {
    health.refetch(); workers.refetch(); stats.refetch(); dashboard.refetch(); queues.refetch();
  };

  return (
    <div className="wg-root">
      <style>{CSS}</style>

      <ConnectionBar baseUrl={baseUrl} setBaseUrl={setBaseUrl} health={health} onRefreshAll={refreshAll} />
      <SystemHealthStrip health={health} workers={workers} stats={stats} />

      <Panel title="GRID PULSE — TASK FLOW" icon={Radio} className="gridpulse-panel">
        <GridPulse queueDepths={queueDepths} workerBusyCount={busyCount} dlqCount={dlqCount} />
      </Panel>

      <div className="wg-grid">
        <div className="wg-col-main">
          <WorkerTable workers={workers} />
          <QueueMonitor queues={queues} stats={stats} />
          <TaskStatistics stats={stats} />
        </div>
        <div className="wg-col-side">
          <AlertsPanel alerts={alerts} />
          <TaskLookup baseUrl={baseUrl} />
        </div>
      </div>

      <footer className="wg-footer mono">
        WorkerGrid v2.0-dev · scheduler.py + priority queue manager in progress · frontend build only
      </footer>
    </div>
  );
}

/* ----------------------------------------------------------------------------
   14. STYLES
---------------------------------------------------------------------------- */

const CSS = `
:root {
  --c-bg: #0A0D12;
  --c-panel: #10141B;
  --c-panel-alt: #0D1117;
  --c-border: #1D232E;
  --c-border-bright: #2B3444;
  --c-text: #DDE3EA;
  --c-text-dim: #6B7684;
  --c-online: #34D399;
  --c-busy: #38BDF8;
  --c-critical: #F87171;
  --c-warning: #FBBF24;
  --c-high: #FB7185;
  --c-medium: #FBBF24;
  --c-low: #60A5FA;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
  --sans: Inter, ui-sans-serif, -apple-system, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
.wg-root {
  background: var(--c-bg);
  color: var(--c-text);
  font-family: var(--sans);
  min-height: 100vh;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background-image:
    linear-gradient(var(--c-border) 1px, transparent 1px),
    linear-gradient(90deg, var(--c-border) 1px, transparent 1px);
  background-size: 32px 32px;
  background-position: -1px -1px;
  background-attachment: local;
}
.mono { font-family: var(--mono); }
.dim { color: var(--c-text-dim); }

/* connection bar */
.connbar {
  display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
  background: var(--c-panel); border: 1px solid var(--c-border); border-radius: 6px;
  padding: 10px 16px;
}
.brand { display: flex; align-items: center; gap: 8px; color: var(--c-text); }
.brand-name { font-family: var(--mono); font-weight: 700; letter-spacing: 1.5px; font-size: 14px; }
.brand-sub { font-size: 10px; letter-spacing: 1.5px; color: var(--c-text-dim); border-left: 1px solid var(--c-border-bright); padding-left: 8px; }
.conn-status { display: flex; align-items: center; gap: 8px; }
.pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--c-text-dim); }
.pulse-dot.up { background: var(--c-online); box-shadow: 0 0 0 3px rgba(52,211,153,0.15); animation: breathe 2.4s ease-in-out infinite; }
.pulse-dot.down { background: var(--c-critical); box-shadow: 0 0 0 3px rgba(248,113,113,0.15); }
.pulse-dot.dim { background: var(--c-text-dim); }
@keyframes breathe { 0%,100% { opacity: 1; } 50% { opacity: 0.45; } }
.conn-text { font-family: var(--mono); font-size: 11px; letter-spacing: 1px; display: flex; align-items: center; gap: 5px; color: var(--c-text-dim); }
.conn-text.up { color: var(--c-online); }
.conn-text.down { color: var(--c-critical); }
.conn-controls { display: flex; align-items: center; gap: 8px; margin-left: auto; flex: 1; min-width: 240px; }
.conn-icon { color: var(--c-text-dim); flex-shrink: 0; }
.conn-input {
  flex: 1; min-width: 120px; background: var(--c-panel-alt); border: 1px solid var(--c-border-bright);
  color: var(--c-text); font-family: var(--mono); font-size: 12px; padding: 6px 10px; border-radius: 4px;
}
.conn-input:focus { outline: none; border-color: var(--c-busy); }
.conn-updated { font-size: 10px; color: var(--c-text-dim); white-space: nowrap; font-family: var(--mono); }
.icon-btn {
  background: var(--c-panel-alt); border: 1px solid var(--c-border-bright); color: var(--c-text);
  padding: 6px 8px; border-radius: 4px; cursor: pointer; display: flex; align-items: center;
}
.icon-btn:hover { border-color: var(--c-busy); color: var(--c-busy); }
.icon-btn:focus-visible { outline: 2px solid var(--c-busy); outline-offset: 1px; }

/* health strip */
.health-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.health-chip {
  background: var(--c-panel); border: 1px solid var(--c-border); border-radius: 6px;
  padding: 10px 12px; display: flex; align-items: center; gap: 10px;
  border-left: 3px solid var(--c-border-bright);
}
.health-chip.tone-healthy { border-left-color: var(--c-online); color: var(--c-online); }
.health-chip.tone-warning { border-left-color: var(--c-warning); color: var(--c-warning); }
.health-chip.tone-critical { border-left-color: var(--c-critical); color: var(--c-critical); }
.health-chip.tone-neutral { border-left-color: var(--c-border-bright); color: var(--c-text); }
.health-chip-value { font-family: var(--mono); font-size: 15px; font-weight: 700; }
.health-chip-label { font-size: 10px; letter-spacing: 1px; color: var(--c-text-dim); margin-top: 2px; }

/* panels */
.panel { background: var(--c-panel); border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; }
.panel-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 10px 14px; border-bottom: 1px solid var(--c-border); background: var(--c-panel-alt);
}
.panel-title { display: flex; align-items: center; gap: 7px; font-size: 11px; letter-spacing: 1.5px; color: var(--c-text-dim); font-weight: 600; }
.panel-body { padding: 14px; }
.panel-count { font-family: var(--mono); font-size: 11px; color: var(--c-text-dim); }
.empty-state { color: var(--c-text-dim); font-size: 12px; font-family: var(--mono); padding: 18px 4px; text-align: center; border: 1px dashed var(--c-border-bright); border-radius: 4px; }

.badge { font-family: var(--mono); font-size: 9px; letter-spacing: 1px; padding: 3px 7px; border-radius: 3px; border: 1px solid; }
.badge-pending { color: var(--c-warning); border-color: var(--c-warning); background: rgba(251,191,36,0.08); }

/* grid pulse */
.gridpulse-panel .panel-body { padding: 6px 10px 10px; }
.gridpulse-wrap { width: 100%; overflow-x: auto; }
.gridpulse-svg { width: 100%; min-width: 620px; height: auto; display: block; }
.gp-node-box { fill: var(--c-panel-alt); stroke: var(--c-border-bright); stroke-width: 1; }
.gp-node-label { fill: var(--c-text-dim); font-family: var(--mono); font-size: 9px; letter-spacing: 1px; }
.gp-node-sub { fill: var(--c-text); font-family: var(--mono); font-size: 10px; }
.gp-node-sub-dim { fill: var(--c-text-dim); font-family: var(--mono); font-size: 8px; }
.gp-lane { stroke-width: 1.5; opacity: 0.55; }
.gp-lane-label { font-family: var(--mono); font-size: 9px; letter-spacing: 0.5px; }
.gp-lane-count { fill: var(--c-text-dim); font-family: var(--mono); font-size: 10px; }
.gp-lane-dlq { stroke: var(--c-critical); stroke-width: 1.5; stroke-dasharray: 3 2; opacity: 0.6; }
.gp-dlq-label { fill: var(--c-critical); font-family: var(--mono); font-size: 8px; letter-spacing: 0.5px; }
@media (prefers-reduced-motion: reduce) { .gp-pulse animateMotion, .pulse-dot.up { animation: none !important; } }

/* layout grid */
.wg-grid { display: grid; grid-template-columns: 2.1fr 1fr; gap: 14px; align-items: start; }
.wg-col-main, .wg-col-side { display: flex; flex-direction: column; gap: 14px; }
@media (max-width: 920px) { .wg-grid { grid-template-columns: 1fr; } }

/* worker table */
.table-scroll { overflow-x: auto; }
.grid-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.grid-table th {
  text-align: left; font-family: var(--mono); font-size: 9px; letter-spacing: 1px; color: var(--c-text-dim);
  padding: 6px 10px; border-bottom: 1px solid var(--c-border-bright); white-space: nowrap;
}
.grid-table td { padding: 8px 10px; border-bottom: 1px solid var(--c-border); white-space: nowrap; }
.grid-table tbody tr:hover { background: var(--c-panel-alt); }
.num-bad { color: var(--c-critical); }
.status-pill { display: inline-flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 10px; letter-spacing: 1px; color: var(--dot); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--dot); box-shadow: 0 0 6px var(--dot); }

/* queue monitor */
.queue-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.queue-card { background: var(--c-panel-alt); border: 1px solid var(--c-border-bright); border-radius: 5px; padding: 10px; }
.queue-card-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; gap: 6px; }
.queue-card-label { font-size: 9px; letter-spacing: 0.5px; font-family: var(--mono); }
.queue-card-value { font-size: 16px; font-weight: 700; }
.queue-bar-track { height: 5px; background: var(--c-border); border-radius: 3px; overflow: hidden; }
.queue-bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
.queue-pending-note { margin-top: 10px; font-size: 11px; color: var(--c-text-dim); font-family: var(--mono); line-height: 1.6; }
.queue-pending-note code { color: var(--c-warning); }

/* task stats */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 10px; }
.stat-cell { background: var(--c-panel-alt); border-left: 3px solid var(--c-border-bright); border-radius: 4px; padding: 10px 12px; }
.stat-cell.tone-busy { border-left-color: var(--c-busy); }
.stat-cell.tone-online { border-left-color: var(--c-online); }
.stat-cell.tone-critical { border-left-color: var(--c-critical); }
.stat-value { font-size: 18px; font-weight: 700; }
.stat-label { font-size: 9px; letter-spacing: 1px; color: var(--c-text-dim); margin-top: 4px; }

/* alerts */
.alert-list { display: flex; flex-direction: column; gap: 8px; list-style: none; margin: 0; padding: 0; }
.alert-row { display: flex; gap: 9px; padding: 8px 10px; background: var(--c-panel-alt); border-radius: 4px; border-left: 3px solid var(--c-border-bright); }
.alert-row.tone-critical { border-left-color: var(--c-critical); }
.alert-row.tone-warning { border-left-color: var(--c-warning); }
.alert-row.tone-info { border-left-color: var(--c-busy); }
.alert-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--c-border-bright); margin-top: 5px; flex-shrink: 0; }
.tone-critical .alert-dot { background: var(--c-critical); }
.tone-warning .alert-dot { background: var(--c-warning); }
.tone-info .alert-dot { background: var(--c-busy); }
.alert-text { font-size: 12px; line-height: 1.4; }
.alert-source { font-size: 9px; color: var(--c-text-dim); margin-top: 3px; }

/* task lookup */
.lookup-row { display: flex; gap: 8px; }
.lookup-input { flex: 1; }
.lookup-status { font-family: var(--mono); font-size: 11px; color: var(--c-text-dim); margin-top: 8px; }
.lookup-status.bad { color: var(--c-critical); }
.lookup-result {
  margin-top: 10px; background: var(--c-panel-alt); border: 1px solid var(--c-border-bright); border-radius: 4px;
  padding: 10px; font-size: 11px; max-height: 220px; overflow: auto; white-space: pre-wrap; word-break: break-word;
}

.wg-footer { text-align: center; font-size: 10px; color: var(--c-text-dim); letter-spacing: 0.5px; padding: 8px 0 2px; }
`;
