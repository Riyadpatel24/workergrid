import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  GitBranch,
  Layers3,
  RefreshCw,
  Search,
  Server,
  Settings2,
  TriangleAlert,
  Users,
  Wifi,
  WifiOff,
  XCircle,
  Zap,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { FrictionDashboard } from "./friction/pages/FrictionDashboard";

const ENDPOINTS = {
  root: "/",
  health: "/health",
  tasks: "/tasks",
  task: (id) => `/tasks/${id}`,
  retryTask: (id) => `/tasks/${id}/retry`,
  cancelTask: (id) => `/tasks/${id}/cancel`,
  workers: "/workers",
  stats: "/stats",
  dashboard: "/dashboard",
  queues: "/queues/priority",
  workflows: "/workflows",
  workflow: (id) => `/workflows/${id}`,
  controlPlane: "/control-plane",
};

function buildUrl(baseUrl, path) {
  return baseUrl ? `${baseUrl.replace(/\/+$/, "")}${path}` : path;
}

async function request(baseUrl, path, { signal, method = "GET", body } = {}) {
  const response = await fetch(buildUrl(baseUrl, path), {
    signal,
    method,
    credentials: "include",  // send HttpOnly auth cookies cross-origin
    headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch { /* response was not JSON */ }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

const api = {
  getRoot: (base, opts) => request(base, ENDPOINTS.root, opts),
  getHealth: (base, opts) => request(base, ENDPOINTS.health, opts),
  getTasks: (base, opts) => request(base, `${ENDPOINTS.tasks}?limit=20`, opts),
  getTask: (base, id, opts) => request(base, ENDPOINTS.task(id), opts),
  getWorkers: (base, opts) => request(base, ENDPOINTS.workers, opts),
  getStats: (base, opts) => request(base, ENDPOINTS.stats, opts),
  getDashboard: (base, opts) => request(base, ENDPOINTS.dashboard, opts),
  getQueues: (base, opts) => request(base, ENDPOINTS.queues, opts),
  getControlPlane: (base, opts) => request(base, ENDPOINTS.controlPlane, opts),
  retryTask: (base, id) => request(base, ENDPOINTS.retryTask(id), { method: "POST" }),
  cancelTask: (base, id) => request(base, ENDPOINTS.cancelTask(id), { method: "POST" }),
};

function usePoll(fn, intervalMs) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const controllerRef = useRef(null);
  const fnRef = useRef(fn);

  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  const run = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      const result = await fnRef.current({ signal: controller.signal });
      setData(result);
      setError(null);
      setUpdatedAt(new Date());
    } catch (error) {
      if (error.name !== "AbortError") setError(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    run();
    if (!intervalMs) return undefined;
    const timer = setInterval(run, intervalMs);
    return () => {
      clearInterval(timer);
      controllerRef.current?.abort();
    };
  }, [run, intervalMs]);

  return { data, error, loading, updatedAt, refetch: run };
}

function useData(baseUrl) {
  return {
    health: usePoll((o) => api.getHealth(baseUrl, o), 5000, [baseUrl]),
    workers: usePoll((o) => api.getWorkers(baseUrl, o), 1000, [baseUrl]),
    stats: usePoll((o) => api.getStats(baseUrl, o), 3000, [baseUrl]),
    dashboard: usePoll((o) => api.getDashboard(baseUrl, o), 3000, [baseUrl]),
    queues: usePoll((o) => api.getQueues(baseUrl, o), 1500, [baseUrl]),
    tasks: usePoll((o) => api.getTasks(baseUrl, { ...o, limit: 20 }), 3000, [baseUrl]),
    control: usePoll((o) => api.getControlPlane(baseUrl, o), 5000, [baseUrl]),
  };
}

function formatDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${Number(seconds).toFixed(2)} s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function formatTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function timeAgo(value) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 2) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}

function workersFrom(data) {
  return Array.isArray(data) ? data : Array.isArray(data?.workers) ? data.workers : [];
}

function statusTone(status) {
  const value = String(status || "").toUpperCase();
  if (value === "SUCCESS") return "success";
  if (value === "FAILED" || value === "CANCELLED") return "danger";
  if (value === "PROCESSING") return "active";
  if (value === "WAITING" || value === "SCHEDULED" || value === "PENDING") return "warning";
  return "neutral";
}

function IconStatus({ status }) {
  const tone = statusTone(status);
  if (tone === "success") return <CheckCircle2 size={15} />;
  if (tone === "danger") return <XCircle size={15} />;
  if (tone === "active") return <Zap size={15} />;
  return <Clock3 size={15} />;
}

function Header({ baseUrl, setBaseUrl, health, refreshAll, activeTab, setActiveTab }) {
  const [draft, setDraft] = useState(baseUrl);
  const healthy = health.data?.status === "healthy";
  return (
    <header className="topbar">
      <div className="brand-wrap">
        <div className="brand-mark"><Layers3 size={19} /></div>
        <div>
          <div className="brand-name">WORKERGRID</div>
          <div className="brand-subtitle">PLATFORM & APPLICATIONS</div>
        </div>
      </div>
      <nav className="nav-tabs">
        <button
          className={`tab-btn ${activeTab === "core" ? "active" : ""}`}
          onClick={() => setActiveTab("core")}
        >
          <Layers3 size={14} />
          <span>Core Platform</span>
          <span className="tab-pill">Engine</span>
        </button>
        <div className="tab-flow-arrow">→</div>
        <button
          className={`tab-btn ${activeTab === "friction" ? "active" : ""}`}
          onClick={() => setActiveTab("friction")}
        >
          <ShieldAlert size={14} />
          <span>Project Friction</span>
          <span className="tab-pill app">App</span>
        </button>
      </nav>
      <div className={`connection ${healthy ? "connection-good" : health.error ? "connection-bad" : "connection-wait"}`}>
        {healthy ? <Wifi size={14} /> : health.error ? <WifiOff size={14} /> : <Activity size={14} />}
        {healthy ? "CONNECTED" : health.error ? "UNREACHABLE" : "CONNECTING"}
      </div>
      <div className="api-control">
        <Settings2 size={13} />
        <input value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => setBaseUrl(draft.trim())} onKeyDown={(e) => e.key === "Enter" && setBaseUrl(draft.trim())} placeholder="API URL (blank = same origin)" />
        <button className="ghost-button" onClick={refreshAll} title="Refresh"><RefreshCw size={14} /></button>
      </div>
    </header>
  );
}

function ProjectFrictionAppCard({ onOpenFriction }) {
  return (
    <div className="friction-app-card">
      <div className="friction-app-content">
        <div className="friction-app-icon"><ShieldAlert size={20} /></div>
        <div className="friction-app-text">
          <div className="eyebrow">APPLICATION USING WORKERGRID</div>
          <h3>Project Friction Workload</h3>
          <p>
            An active developer-friction analytics application executing 4-stage DAG workflows on this WorkerGrid instance (GitHub data collection → metrics calculation → report generation).
          </p>
        </div>
      </div>
      <button className="primary-button flex-btn" onClick={onOpenFriction}>
        <ShieldAlert size={13} />
        <span>Open Project Friction</span>
      </button>
    </div>
  );
}

function Hero({ dashboard, stats }) {
  const system = dashboard.data?.system_status || (stats.error ? "CRITICAL" : "HEALTHY");
  const tone = system === "HEALTHY" ? "success" : system === "WARNING" ? "warning" : "danger";
  const copy = tone === "success" ? "Everything is operating normally." : tone === "warning" ? "The system is running, but some items need attention." : "The platform needs attention.";
  return (
    <section className={`hero-card ${tone}`}>
      <div>
        <div className="eyebrow">SYSTEM OVERVIEW</div>
        <div className="hero-title"><IconStatus status={tone === "success" ? "SUCCESS" : tone === "warning" ? "WAITING" : "FAILED"} /> {system}</div>
        <p>{copy}</p>
      </div>
      <div className="hero-meta">
        <span>Last update</span>
        <strong>{timeAgo(dashboard.updatedAt)}</strong>
      </div>
    </section>
  );
}

function MetricCard({ label, value, note, tone = "neutral", icon: Icon }) {
  return (
    <div className={`metric-card ${tone}`}>
      <div className="metric-icon"><Icon size={17} /></div>
      <div className="metric-value">{value ?? "—"}</div>
      <div className="metric-label">{label}</div>
      {note && <div className="metric-note">{note}</div>}
    </div>
  );
}

function Overview({ stats }) {
  const s = stats.data || {};
  const workers = s.workers || {};
  const tasks = s.tasks || {};
  return (
    <div className="metric-grid">
      <MetricCard icon={Users} label="Workers available" value={workers.online ?? 0} note={`${workers.busy ?? 0} currently busy`} tone="success" />
      <MetricCard icon={Zap} label="Tasks processing" value={tasks.processing ?? 0} note="being handled right now" tone="active" />
      <MetricCard icon={Layers3} label="Tasks waiting" value={(tasks.queued ?? 0) + (tasks.pending ?? 0) + (tasks.scheduled ?? 0)} note={`${tasks.scheduled ?? 0} scheduled`} tone="warning" />
      <MetricCard icon={CheckCircle2} label="Completed" value={tasks.successful ?? 0} note={`${tasks.failed ?? 0} failed`} tone="success" />
    </div>
  );
}

function ActiveTasks({ workers, tasks }) {
  const workerList = workersFrom(workers.data);
  const active = workerList.filter((worker) => worker.current_task != null);
  const activeTaskMap = new Map((tasks.data?.items || []).map((task) => [task.id, task]));
  return (
    <Panel title="WHAT IS HAPPENING NOW" icon={Activity} right={<span className="panel-badge">LIVE</span>}>
      {active.length === 0 ? (
        <Empty label="No tasks are currently being processed." />
      ) : (
        <div className="active-list">
          {active.map((worker) => {
            const task = activeTaskMap.get(worker.current_task);
            return (
              <div className="active-card" key={worker.worker_id}>
                <div className="active-pulse" />
                <div className="active-main">
                  <div className="active-title">Task #{worker.current_task}</div>
                  <div className="active-sub">{task?.type || "Task is being processed"}</div>
                </div>
                <div className="active-worker">
                  <span>Assigned worker</span>
                  <strong>#{worker.worker_id}</strong>
                </div>
                <div className="active-status">BUSY</div>
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

function WorkerTable({ workers }) {
  const list = workersFrom(workers.data);
  return (
    <Panel title="WORKERS" icon={Server} right={<span className="panel-badge">{list.length} registered</span>}>
      {workers.error ? <Empty label="Worker information is temporarily unavailable." /> : list.length === 0 ? <Empty label="No workers are currently registered." /> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>WORKER</th><th>STATUS</th><th>CURRENT TASK</th><th>COMPLETED</th><th>FAILED</th><th>CAPABILITIES</th></tr></thead>
            <tbody>
              {list.map((worker) => {
                const active = worker.current_task != null;
                return (
                  <tr className={active ? "worker-active" : ""} key={worker.worker_id}>
                    <td><strong className="mono">#{worker.worker_id}</strong><div className="subtle mono">{worker.hostname}</div></td>
                    <td><StatusBadge status={worker.status} /></td>
                    <td>{active ? <span className="task-link">Task #{worker.current_task}</span> : <span className="subtle">Idle</span>}</td>
                    <td className="mono">{worker.completed_tasks ?? 0}</td>
                    <td className={`mono ${worker.failed_tasks > 0 ? "danger-text" : ""}`}>{worker.failed_tasks ?? 0}</td>
                    <td className="subtle">{(worker.capabilities || []).join(", ") || "general"}</td>
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

function QueuePanel({ queues, stats }) {
  const q = queues.data || stats.data?.priority_queues || {};
  const items = [
    ["High priority", q.high ?? 0, "high"],
    ["Normal priority", q.medium ?? 0, "medium"],
    ["Low priority", q.low ?? 0, "low"],
    ["Needs attention", q.dead_letter ?? stats.data?.tasks?.dead_letter ?? 0, "danger"],
  ];
  return (
    <Panel title="WORK WAITING TO BE PROCESSED" icon={Layers3}>
      <div className="queue-grid">
        {items.map(([label, value, tone]) => (
          <div className={`queue-item ${tone}`} key={label}>
            <div className="queue-label">{label}</div>
            <div className="queue-value">{value}</div>
            <div className="queue-caption">{tone === "danger" ? "tasks need attention" : "tasks waiting"}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RecentActivity({ tasks, onSelect }) {
  const items = tasks.data?.items || [];
  return (
    <Panel title="RECENT ACTIVITY" icon={Clock3}>
      {tasks.error ? <Empty label="Recent task activity is unavailable." /> : items.length === 0 ? <Empty label="No task activity yet." /> : (
        <div className="activity-list">
          {items.slice(0, 10).map((task) => (
            <button className="activity-row" key={task.id} onClick={() => onSelect(task.id)}>
              <span className={`activity-icon ${statusTone(task.status)}`}><IconStatus status={task.status} /></span>
              <span className="activity-main"><strong>Task #{task.id}</strong><span>{task.type}</span></span>
              <span className="activity-meta"><strong>{task.status}</strong><span>{timeAgo(task.created_at)}</span></span>
            </button>
          ))}
        </div>
      )}
    </Panel>
  );
}

function TaskLookup({ baseUrl, selectedId, onSelected }) {
  const [taskId, setTaskId] = useState(selectedId ? String(selectedId) : "");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState(null);

  useEffect(() => {
    if (selectedId) void lookupTask(selectedId);
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function lookupTask(id = taskId) {
    if (!String(id).trim()) return;
    setLoading(true); setError(null);
    try { const data = await api.getTask(baseUrl, id); setResult(data); onSelected?.(data); }
    catch (err) { setResult(null); setError(err); }
    finally { setLoading(false); }
  }

  async function runAction(kind) {
    if (!result) return;
    setAction(kind);
    try {
      const data = kind === "retry" ? await api.retryTask(baseUrl, result.id) : await api.cancelTask(baseUrl, result.id);
      setResult(data);
      onSelected?.(data);
    } catch (err) { setError(err); }
    finally { setAction(null); }
  }

  return (
    <Panel title="TASK DETAILS" icon={Search}>
      <div className="lookup-row">
        <input value={taskId} onChange={(e) => setTaskId(e.target.value)} onKeyDown={(e) => e.key === "Enter" && lookupTask()} placeholder="Enter a task ID" />
        <button className="primary-button" onClick={() => lookupTask()} disabled={loading}>{loading ? "…" : "View task"}</button>
      </div>
      {error && <div className="error-box">{error.message}</div>}
      {result && (
        <div className="task-detail">
          <div className="detail-header">
            <div><div className="eyebrow">TASK</div><h3>#{result.id}</h3></div>
            <StatusBadge status={result.status} />
          </div>
          <div className="detail-grid">
            <Detail label="Type" value={result.type} />
            <Detail label="Priority" value={result.priority} />
            <Detail label="Worker" value={result.worker_id ? `#${result.worker_id}` : "Not assigned yet"} />
            <Detail label="Processing time" value={formatDuration(result.processing_time)} />
            <Detail label="Started" value={formatTime(result.started_at)} />
            <Detail label="Completed" value={formatTime(result.completed_at)} />
          </div>
          <div className="detail-actions">
            {(result.status === "FAILED" || result.status === "SUCCESS") && <button className="secondary-button" onClick={() => runAction("retry")} disabled={!!action}>{action === "retry" ? "Retrying…" : "Retry task"}</button>}
            {!['SUCCESS', 'FAILED', 'CANCELLED'].includes(result.status) && <button className="danger-button" onClick={() => runAction("cancel")} disabled={!!action}>{action === "cancel" ? "Cancelling…" : "Cancel task"}</button>}
          </div>
          <details className="technical-details">
            <summary>Technical details</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}
    </Panel>
  );
}

function ControlPlane({ control }) {
  const resources = control.data?.resources || {};
  const scaling = control.data?.scaling || {};
  return (
    <Panel title="ADVANCED SYSTEM DETAILS" icon={Settings2}>
      {control.error ? <Empty label="Control-plane metrics are unavailable." /> : (
        <div className="advanced-grid">
          <Detail label="CPU usage" value={resources.cpu_percent == null ? "Unavailable" : `${resources.cpu_percent}%`} />
          <Detail label="Memory usage" value={resources.memory_percent == null ? "Unavailable" : `${resources.memory_percent}%`} />
          <Detail label="Workers online" value={resources.workers_online ?? "—"} />
          <Detail label="Workers busy" value={resources.workers_busy ?? "—"} />
          <Detail label="Waiting work" value={resources.queue_waiting ?? "—"} />
          <Detail label="Recommended workers" value={scaling.recommended_workers ?? "—"} />
          <Detail label="Scaling mode" value={scaling.mode || "—"} />
        </div>
      )}
      <div className="advanced-note">Scaling recommendations are advisory. Worker deployment remains an infrastructure responsibility.</div>
    </Panel>
  );
}

function Alerts({ dashboard }) {
  const alerts = dashboard.data?.alerts || [];
  return (
    <Panel title="NEEDS ATTENTION" icon={TriangleAlert} right={<span className="panel-badge">{alerts.length}</span>}>
      {alerts.length === 0 ? <div className="all-good"><CheckCircle2 size={16} /> No active issues.</div> : (
        <div className="alert-list">{alerts.map((alert, index) => <div className={`alert ${alert.level}`} key={`${alert.message}-${index}`}><AlertTriangle size={15} /><span>{alert.message}</span></div>)}</div>
      )}
    </Panel>
  );
}

function WorkflowSummary({ dashboard }) {
  const active = dashboard.data?.active_tasks || [];
  const workflows = active.filter((task) => task.workflow_id);
  return (
    <Panel title="WORKFLOW ACTIVITY" icon={GitBranch} right={<span className="panel-badge">v3</span>}>
      {workflows.length === 0 ? <Empty label="No workflow steps are currently processing." /> : workflows.map((task) => <div className="workflow-row" key={task.id}><strong>{task.workflow_key || `Task #${task.id}`}</strong><span>{task.workflow_id}</span><StatusBadge status={task.status} /></div>)}
    </Panel>
  );
}

function StatusBadge({ status }) {
  const tone = statusTone(status);
  return <span className={`status-badge ${tone}`}><span />{status || "UNKNOWN"}</span>;
}

function Detail({ label, value }) {
  return <div className="detail"><span>{label}</span><strong>{value ?? "—"}</strong></div>;
}

function Empty({ label }) { return <div className="empty">{label}</div>; }

function Panel({ title, icon: Icon, right, children }) {
  return <section className="panel"><div className="panel-head"><div className="panel-title">{Icon && <Icon size={15} />}<span>{title}</span></div>{right}</div><div className="panel-body">{children}</div></section>;
}

// VITE_API_URL is injected at build time (set it in your .env or Vercel dashboard).
// Falls back to empty string so the UI's manual URL field still works for local dev.
const _DEFAULT_API_URL = import.meta.env.VITE_API_URL || "";

export default function App() {
  const [baseUrl, setBaseUrl] = useState(_DEFAULT_API_URL);
  const [activeTab, setActiveTab] = useState("core");
  const [selectedTask, setSelectedTask] = useState(null);
  const data = useData(baseUrl);
  const refreshAll = () => Object.values(data).forEach((item) => item.refetch());
  const stats = data.stats.data || {};

  return (
    <div className="app-shell">
      <Header
        baseUrl={baseUrl}
        setBaseUrl={setBaseUrl}
        health={data.health}
        refreshAll={refreshAll}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />
      <main>
        {activeTab === "friction" ? (
          <FrictionDashboard baseUrl={baseUrl} onSwitchToCore={() => setActiveTab("core")} />
        ) : (
          <>
            <Hero dashboard={data.dashboard} stats={data.stats} />
            <ProjectFrictionAppCard onOpenFriction={() => setActiveTab("friction")} />
            <Overview stats={data.stats} />
            <div className="two-column">
              <div className="main-column">
                <ActiveTasks workers={data.workers} tasks={data.tasks} />
                <RecentActivity tasks={data.tasks} onSelect={(id) => setSelectedTask(id)} />
                <WorkerTable workers={data.workers} />
                <QueuePanel queues={data.queues} stats={data.stats} />
                <ControlPlane control={data.control} />
              </div>
              <aside className="side-column">
                <Alerts dashboard={data.dashboard} />
                <TaskLookup key={selectedTask ?? "lookup"} baseUrl={baseUrl} selectedId={selectedTask} onSelected={setSelectedTask} />
                <WorkflowSummary dashboard={data.dashboard} />
                <Panel title="PERFORMANCE" icon={Database}>
                  <div className="advanced-grid">
                    <Detail label="Successful" value={stats.performance?.successful ?? 0} />
                    <Detail label="Failed" value={stats.performance?.failed ?? 0} />
                    <Detail label="Average processing" value={formatDuration(stats.performance?.average_processing_time)} />
                    <Detail label="Workers busy" value={stats.workers?.busy ?? 0} />
                  </div>
                </Panel>
              </aside>
            </div>
          </>
        )}
      </main>
      <footer>WorkerGrid v3.0 · distributed task processing · client console + Project Friction</footer>
    </div>
  );
}

const CSS = `
:root{--bg:#070a0f;--panel:#0d1219;--panel2:#101722;--border:#202a36;--border2:#2d3a4a;--text:#e6edf5;--muted:#8190a0;--green:#34d399;--blue:#38bdf8;--yellow:#fbbf24;--red:#f87171;--purple:#a78bfa;--mono:ui-monospace,SFMono-Regular,Consolas,monospace;--sans:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}.app-shell{min-height:100vh;background:radial-gradient(circle at 50% -20%,#162232 0,#070a0f 42%);color:var(--text);font-family:var(--sans);padding:18px;line-height:1.4}.app-shell main{max-width:1400px;margin:auto}.topbar{max-width:1400px;margin:0 auto 16px;display:flex;align-items:center;gap:18px;padding:11px 14px;background:rgba(13,18,25,.94);border:1px solid var(--border);border-radius:8px;position:sticky;top:10px;z-index:10;backdrop-filter:blur(12px)}.brand-wrap{display:flex;align-items:center;gap:10px}.brand-mark{width:34px;height:34px;border:1px solid var(--border2);display:grid;place-items:center;border-radius:6px;color:var(--blue)}.brand-name{font:700 14px var(--mono);letter-spacing:1.5px}.brand-subtitle{font-size:9px;color:var(--muted);letter-spacing:1.3px}.connection{display:flex;align-items:center;gap:6px;font:600 10px var(--mono);padding:6px 9px;border:1px solid var(--border);border-radius:4px}.connection-good{color:var(--green)}.connection-bad{color:var(--red)}.connection-wait{color:var(--yellow)}.api-control{display:flex;align-items:center;gap:7px;margin-left:auto;min-width:320px;flex:1;max-width:580px;color:var(--muted)}.api-control input,.lookup-row input{flex:1;min-width:0;background:#080c11;color:var(--text);border:1px solid var(--border2);border-radius:4px;padding:8px 10px;font:11px var(--mono)}button{border:0}.ghost-button,.primary-button,.secondary-button,.danger-button{border-radius:4px;padding:8px 11px;font-size:11px}.ghost-button{background:#0a0f15;color:var(--text);border:1px solid var(--border2)}.primary-button{background:var(--blue);color:#041018;font-weight:700}.secondary-button{background:#111b25;color:var(--text);border:1px solid var(--border2)}.danger-button{background:transparent;color:var(--red);border:1px solid rgba(248,113,113,.45)}.hero-card{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:22px;border:1px solid var(--border);border-left:4px solid var(--green);background:linear-gradient(90deg,#0f171f,#0c1118);border-radius:8px}.hero-card.warning{border-left-color:var(--yellow)}.hero-card.danger{border-left-color:var(--red)}.eyebrow{font:600 9px var(--mono);letter-spacing:1.5px;color:var(--muted);margin-bottom:5px}.hero-title{display:flex;align-items:center;gap:8px;font:700 22px var(--mono)}.hero-card.success .hero-title{color:var(--green)}.hero-card.warning .hero-title{color:var(--yellow)}.hero-card.danger .hero-title{color:var(--red)}.hero-card p{margin:6px 0 0;color:var(--muted);font-size:13px}.hero-meta{font:10px var(--mono);color:var(--muted);text-align:right}.hero-meta strong{display:block;color:var(--text);margin-top:3px}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}.metric-card{padding:16px;background:var(--panel);border:1px solid var(--border);border-radius:7px;min-height:126px;border-top:2px solid var(--border2)}.metric-card.success{border-top-color:var(--green)}.metric-card.active{border-top-color:var(--blue)}.metric-card.warning{border-top-color:var(--yellow)}.metric-icon{color:var(--muted)}.metric-value{font:700 27px var(--mono);margin-top:8px}.metric-label{font-size:11px;color:var(--text);font-weight:600}.metric-note{font-size:10px;color:var(--muted);margin-top:3px}.two-column{display:grid;grid-template-columns:minmax(0,2fr) minmax(320px,1fr);gap:12px}.main-column,.side-column{display:flex;flex-direction:column;gap:12px}.panel{background:rgba(13,18,25,.96);border:1px solid var(--border);border-radius:7px;overflow:hidden}.panel-head{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;border-bottom:1px solid var(--border);background:#0b1016}.panel-title{display:flex;align-items:center;gap:7px;color:var(--muted);font:600 10px var(--mono);letter-spacing:1.2px}.panel-badge{font:9px var(--mono);color:var(--blue);border:1px solid rgba(56,189,248,.25);padding:3px 6px;border-radius:3px}.panel-body{padding:13px}.active-list{display:flex;flex-direction:column;gap:8px}.active-card{display:grid;grid-template-columns:8px 1fr auto auto;align-items:center;gap:12px;padding:13px;background:#0b1118;border:1px solid rgba(56,189,248,.22);border-radius:5px;box-shadow:inset 3px 0 var(--blue)}.active-pulse{width:7px;height:7px;background:var(--blue);border-radius:5px;box-shadow:0 0 0 5px rgba(56,189,248,.08);animation:pulse 1.4s infinite}.active-title{font:700 13px var(--mono)}.active-sub{font-size:11px;color:var(--muted)}.active-worker span{display:block;color:var(--muted);font-size:9px}.active-worker strong{font:600 11px var(--mono)}.active-status{color:var(--blue);font:700 9px var(--mono)}@keyframes pulse{50%{opacity:.35;transform:scale(.7)}}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:11px}th{text-align:left;color:var(--muted);font:600 9px var(--mono);letter-spacing:1px;padding:8px;border-bottom:1px solid var(--border);white-space:nowrap}td{padding:10px 8px;border-bottom:1px solid #18202a;white-space:nowrap}tbody tr:hover{background:#0f161e}.worker-active{background:rgba(56,189,248,.06);box-shadow:inset 3px 0 var(--blue)}.mono{font-family:var(--mono)}.subtle{color:var(--muted);font-size:9px}.task-link{color:var(--blue);font:600 10px var(--mono)}.danger-text{color:var(--red)}.status-badge{display:inline-flex;align-items:center;gap:5px;font:600 9px var(--mono);letter-spacing:.6px}.status-badge span{width:6px;height:6px;border-radius:50%;background:var(--muted)}.status-badge.success{color:var(--green)}.status-badge.success span{background:var(--green)}.status-badge.active{color:var(--blue)}.status-badge.active span{background:var(--blue)}.status-badge.warning{color:var(--yellow)}.status-badge.warning span{background:var(--yellow)}.status-badge.danger{color:var(--red)}.status-badge.danger span{background:var(--red)}.queue-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.queue-item{padding:12px;background:#0b1118;border:1px solid var(--border);border-radius:5px}.queue-item.high{border-top:2px solid #fb7185}.queue-item.medium{border-top:2px solid var(--yellow)}.queue-item.low{border-top:2px solid #60a5fa}.queue-item.danger{border-top:2px solid var(--red)}.queue-label{font-size:10px;color:var(--muted)}.queue-value{font:700 22px var(--mono);margin-top:4px}.queue-caption{font-size:9px;color:var(--muted)}.activity-list{display:flex;flex-direction:column}.activity-row{display:grid;grid-template-columns:30px 1fr auto;align-items:center;gap:9px;text-align:left;background:transparent;color:var(--text);padding:9px 3px;border-bottom:1px solid #18202a}.activity-row:hover{background:#0f161e}.activity-icon{width:27px;height:27px;display:grid;place-items:center;border-radius:4px}.activity-icon.success{color:var(--green);background:rgba(52,211,153,.08)}.activity-icon.active{color:var(--blue);background:rgba(56,189,248,.08)}.activity-icon.warning{color:var(--yellow);background:rgba(251,191,36,.08)}.activity-icon.danger{color:var(--red);background:rgba(248,113,113,.08)}.activity-main span,.activity-meta span{display:block;color:var(--muted);font-size:9px}.activity-main strong,.activity-meta strong{font:600 10px var(--mono)}.activity-meta{text-align:right}.lookup-row{display:flex;gap:7px}.error-box{margin-top:8px;padding:8px;background:rgba(248,113,113,.07);border:1px solid rgba(248,113,113,.2);color:var(--red);font:10px var(--mono)}.task-detail{margin-top:12px;border:1px solid var(--border);background:#0a1016;border-radius:5px;padding:12px}.detail-header{display:flex;justify-content:space-between;align-items:center}.detail-header h3{margin:0;font:700 20px var(--mono)}.detail-grid,.advanced-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:12px}.detail{padding:8px;background:#0e151d;border:1px solid #18222d;border-radius:4px}.detail span{display:block;color:var(--muted);font-size:9px}.detail strong{display:block;margin-top:3px;font:600 10px var(--mono);overflow-wrap:anywhere}.detail-actions{display:flex;gap:7px;margin-top:10px}.technical-details{margin-top:10px;color:var(--muted);font-size:10px}.technical-details summary{cursor:pointer}.technical-details pre{white-space:pre-wrap;word-break:break-word;max-height:240px;overflow:auto;background:#070b10;border:1px solid var(--border);padding:9px;color:#b9c6d4;font:9px var(--mono)}.advanced-note{margin-top:10px;color:var(--muted);font-size:9px;line-height:1.5}.alert-list{display:flex;flex-direction:column;gap:7px}.alert{display:flex;align-items:flex-start;gap:7px;padding:9px;border-left:3px solid var(--yellow);background:#0b1118;color:#dbe4ed;font-size:11px}.alert.critical{border-left-color:var(--red)}.alert.warning{border-left-color:var(--yellow)}.all-good{display:flex;align-items:center;gap:7px;color:var(--green);font-size:11px;padding:5px}.workflow-row{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #18202a}.workflow-row strong{font:600 10px var(--mono)}.workflow-row span:not(.status-badge){color:var(--muted);font:9px var(--mono)}.empty{padding:20px 8px;text-align:center;border:1px dashed var(--border2);color:var(--muted);font-size:11px}.app-shell footer{max-width:1400px;margin:12px auto 0;color:#566473;text-align:center;font:9px var(--mono);letter-spacing:.5px}@media(max-width:1050px){.metric-grid{grid-template-columns:repeat(2,1fr)}.two-column{grid-template-columns:1fr}.api-control{min-width:220px}}@media(max-width:680px){.app-shell{padding:9px}.topbar{position:static;flex-wrap:wrap}.connection{order:3}.api-control{min-width:100%;max-width:none}.metric-grid{grid-template-columns:1fr 1fr}.queue-grid{grid-template-columns:1fr 1fr}.active-card{grid-template-columns:8px 1fr}.active-worker,.active-status{grid-column:2}.detail-grid,.advanced-grid{grid-template-columns:1fr}}
.nav-tabs{display:flex;align-items:center;gap:6px;margin-left:12px}.tab-btn{display:flex;align-items:center;gap:6px;background:transparent;color:var(--muted);border:1px solid var(--border);padding:6px 12px;border-radius:5px;font:600 11px var(--sans);cursor:pointer;transition:all .2s}.tab-btn:hover{color:var(--text);border-color:var(--border2)}.tab-btn.active{background:rgba(56,189,248,.12);color:var(--blue);border-color:rgba(56,189,248,.4)}
.tab-pill{font:600 8px var(--mono);padding:1px 5px;border-radius:3px;background:rgba(255,255,255,.08);color:var(--muted);text-transform:uppercase}.tab-pill.app{background:rgba(56,189,248,.15);color:var(--blue)}.tab-flow-arrow{color:var(--muted);font:600 12px var(--mono);opacity:.6;user-select:none}
.flex-btn{display:inline-flex;align-items:center;gap:6px;cursor:pointer}
.friction-app-card{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:16px 20px;margin:12px 0;background:linear-gradient(90deg,#0f1927,#0a111a);border:1px solid rgba(56,189,248,.25);border-radius:8px;box-shadow:inset 3px 0 var(--blue)}
.friction-app-content{display:flex;align-items:center;gap:14px}
.friction-app-icon{width:38px;height:38px;border-radius:6px;background:rgba(56,189,248,.12);border:1px solid rgba(56,189,248,.3);display:grid;place-items:center;color:var(--blue);flex-shrink:0}
.friction-app-text h3{margin:2px 0 0;font:700 15px var(--mono);color:var(--text)}
.friction-app-text p{margin:4px 0 0;font-size:12px;color:var(--muted);max-width:720px}
.friction-dashboard-shell{display:flex;flex-direction:column;gap:16px}.friction-card{background:rgba(13,18,25,.96);border:1px solid var(--border);border-radius:8px;padding:16px}.friction-card-title{display:flex;align-items:center;gap:8px;font:600 11px var(--mono);color:var(--muted);letter-spacing:1.2px;margin-bottom:14px;position:relative}.right-btn{margin-left:auto;padding:4px 8px}
.how-workergrid-card{border:1px solid rgba(56,189,248,.3);background:linear-gradient(180deg,#0e1622,#090e15)}.how-header{display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none}.how-title-wrap{display:flex;align-items:center;gap:12px}.how-title{margin:0;font:700 15px var(--mono);color:var(--text)}.how-body{margin-top:16px;padding-top:16px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:16px}.how-intro{font-size:13px;color:var(--text);line-height:1.5;margin:0}.concepts-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.concept-card{padding:12px;background:#060a0f;border:1px solid var(--border);border-radius:6px}.concept-head{display:flex;align-items:center;gap:8px;font:700 12px var(--mono);margin-bottom:6px}.concept-card p{font-size:11px;color:var(--muted);margin:0;line-height:1.4}.how-subheading{font:700 11px var(--mono);color:var(--muted);letter-spacing:1.2px;margin:8px 0 0}.diagram-box{display:flex;flex-direction:column;align-items:center;gap:8px;padding:20px;background:#05080c;border:1px dashed var(--border2);border-radius:8px}.diagram-node{padding:10px 20px;border-radius:6px;text-align:center;width:100%;max-width:420px;border:1px solid var(--border);background:#0b1118}.node-gh{border-color:rgba(167,139,250,.4)}.node-pf{border-color:rgba(56,189,248,.4)}.node-wg{border-color:rgba(251,191,36,.4)}.node-ui{border-color:rgba(52,211,153,.4)}.diagram-arrow{color:var(--muted)}.diagram-stage-container{width:100%;max-width:540px;display:flex;flex-direction:column;gap:8px;padding:12px;background:#0a0f16;border:1px solid var(--border2);border-radius:6px}.stage-item{display:flex;align-items:flex-start;gap:12px;padding:8px;background:#060a0e;border-radius:4px}.stage-num{font:700 11px var(--mono);color:var(--blue);background:rgba(56,189,248,.12);padding:2px 8px;border-radius:4px;border:1px solid rgba(56,189,248,.25)}.stage-content strong{display:block;font-size:12px;color:var(--text)}.stage-content p{margin:2px 0 0;font-size:11px;color:var(--muted)}.how-footer-note{display:flex;align-items:center;gap:8px;padding:10px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);border-radius:6px;font-size:11px;color:var(--text)}
.selector-form{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap}.form-group{display:flex;flex-direction:column;gap:5px}.form-group label{font:600 10px var(--mono);color:var(--muted)}.flex-1{flex:1;min-width:140px}.flex-2{flex:2;min-width:220px}.selector-form input,.selector-form select{background:#080c11;border:1px solid var(--border2);color:var(--text);padding:8px 10px;border-radius:5px;font:11px var(--mono);width:100%}.select-wrap{position:relative;display:flex;align-items:center}.select-icon{position:absolute;left:10px;color:var(--muted);pointer-events:none}.select-wrap select{padding-left:30px}.run-btn{display:flex;align-items:center;gap:6px;height:35px;padding:0 16px}.recent-repos{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid var(--border);flex-wrap:wrap}.chip-btn{background:#111822;color:var(--blue);border:1px solid var(--border2);font:10px var(--mono);padding:3px 8px;border-radius:4px;cursor:pointer}.chip-btn:hover{background:rgba(56,189,248,.15)}
.progress-card{border-left:4px solid var(--blue)}.progress-card.completed{border-left-color:var(--green)}.progress-card.failed{border-left-color:var(--red)}.progress-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.progress-title{display:flex;align-items:center;gap:10px}.progress-track-wrap{display:flex;flex-direction:column;gap:6px}.progress-info{display:flex;justify-content:space-between;font:11px var(--mono);color:var(--muted)}.progress-track{height:8px;background:#090e15;border-radius:4px;overflow:hidden;border:1px solid var(--border)}.progress-fill{height:100%;transition:width .3s ease}.fill-blue{background:var(--blue)}.fill-green{background:var(--green)}.fill-red{background:var(--red)}.text-green{color:var(--green)}.text-red{color:var(--red)}.text-blue{color:var(--blue)}.spin{animation:spin 1.2s linear infinite}@keyframes spin{100%{transform:rotate(360deg)}}
.scorecard-container{display:flex;flex-direction:column;gap:14px;margin-bottom:16px}.scorecard-hero{display:flex;align-items:center;gap:24px;padding:24px;border-radius:8px;border:1px solid var(--border);background:linear-gradient(90deg,#0e1622,#0a0f17)}.scorecard-hero.success{border-left:5px solid var(--green)}.scorecard-hero.warning{border-left:5px solid var(--yellow)}.scorecard-hero.danger{border-left:5px solid var(--red)}.gauge-wrap{display:flex;align-items:baseline;gap:4px;padding:16px 20px;background:#06090d;border:1px solid var(--border2);border-radius:8px}.score-number{font:700 42px var(--mono);color:var(--text)}.score-max{font:12px var(--mono);color:var(--muted)}.dimensions-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.dimension-card{padding:14px;background:var(--panel);border:1px solid var(--border);border-radius:7px;border-top:3px solid var(--border2)}.dimension-card.good{border-top-color:var(--green)}.dimension-card.warn{border-top-color:var(--yellow)}.dimension-card.bad{border-top-color:var(--red)}.dim-head{display:flex;align-items:center;gap:7px;font:600 10px var(--mono);color:var(--muted)}.dim-value{font:700 24px var(--mono);margin:8px 0 2px}.dim-caption{font-size:9px;color:var(--muted)}
.report-view{display:flex;flex-direction:column;gap:16px}.report-topbar{display:flex;align-items:center;gap:14px}.back-btn{display:flex;align-items:center;gap:6px}.report-title-meta h3{margin:0;font:700 18px var(--mono)}.section-title{font:700 11px var(--mono);color:var(--muted);letter-spacing:1.2px;margin:8px 0 10px}.indicators-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}.indicator-card{padding:16px;background:#0d131c;border:1px solid var(--border);border-radius:7px;display:flex;flex-direction:column;gap:10px;border-left:4px solid var(--blue)}.indicator-card.danger{border-left-color:var(--red)}.indicator-card.warning{border-left-color:var(--yellow)}.indicator-header{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.indicator-title-wrap{display:flex;align-items:center;gap:8px}.indicator-title-wrap h4{margin:0;font:700 13px var(--mono)}.severity-badge{font:700 9px var(--mono);padding:3px 7px;border-radius:3px}.severity-badge.danger{background:rgba(248,113,113,.15);color:var(--red);border:1px solid rgba(248,113,113,.3)}.severity-badge.warning{background:rgba(251,191,36,.15);color:var(--yellow);border:1px solid rgba(251,191,36,.3)}.severity-badge.info{background:rgba(56,189,248,.15);color:var(--blue);border:1px solid rgba(56,189,248,.3)}.indicator-summary{font-size:12px;color:var(--text);margin:0}.recommendation-box{padding:10px;background:#080c12;border:1px solid #16202c;border-radius:5px;font-size:11px;color:var(--muted)}.recommendation-box strong{color:var(--blue);display:block;margin-bottom:3px}.indicator-footer{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:8px;border-top:1px solid #16202c}.evidence-btn{display:flex;align-items:center;gap:5px;font-weight:600;color:var(--blue)}
.metrics-list-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.metric-detail-item{padding:12px;background:#090e15;border:1px solid var(--border);border-radius:6px}.metric-header-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}.metric-category-chip{font:600 8px var(--mono);color:var(--muted);background:#101824;padding:2px 6px;border-radius:3px;text-transform:uppercase}.metric-val{font:700 14px var(--mono);color:var(--blue)}.metric-name-text{font-size:11px;font-weight:600;color:var(--text)}.metric-details-meta{font-size:9px;color:var(--muted);margin-top:4px}
.modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.75);backdrop-filter:blur(4px);display:grid;place-items:center;z-index:100;padding:16px}.modal-content{width:100%;max-width:680px;background:#0c1219;border:1px solid var(--border);border-radius:8px;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,.6)}.modal-header{display:flex;justify-content:space-between;align-items:flex-start;padding:16px 20px;background:#090d13;border-bottom:1px solid var(--border)}.modal-header h3{margin:0;font:700 16px var(--mono)}.modal-body{padding:20px;max-height:70vh;overflow-y:auto}.evidence-list{display:flex;flex-direction:column;gap:10px;margin-top:14px}.evidence-row{display:flex;align-items:center;gap:12px;padding:12px;background:#080c11;border:1px solid #18222e;border-radius:6px}.evidence-icon{color:var(--blue)}.evidence-main{flex:1;min-width:0}.evidence-title{font-size:12px}.evidence-breakdown{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}.chip{font-size:9px;background:#101722;color:var(--muted);padding:2px 6px;border-radius:3px}.link-btn{display:flex;align-items:center;gap:5px;font-size:10px}.modal-footer{padding:12px 20px;background:#090d13;border-top:1px solid var(--border);display:flex;justify-content:flex-end}.row-selected{background:rgba(56,189,248,.08)!important}.score-chip{font:700 10px var(--mono);padding:3px 8px;border-radius:4px}.score-chip.low{background:rgba(52,211,153,.15);color:var(--green)}.score-chip.medium{background:rgba(251,191,36,.15);color:var(--yellow)}.score-chip.high,.score-chip.critical{background:rgba(248,113,113,.15);color:var(--red)}
@media(prefers-reduced-motion:reduce){.active-pulse{animation:none}}
`;

// Keep the product styling self-contained so the supplied frontend can be dropped in
// without depending on a CSS framework.
if (typeof document !== "undefined") {
  const style = document.createElement("style");
  style.dataset.workergrid = "v3";
  style.textContent = CSS;
  document.head.appendChild(style);
}
