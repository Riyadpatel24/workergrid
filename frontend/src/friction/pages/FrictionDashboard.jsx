import { useState, useEffect, useCallback, useRef } from "react";
import { frictionApi } from "../api/frictionApi";
import { RepositorySelector } from "../components/RepositorySelector";
import { AnalysisProgress } from "../components/AnalysisProgress";
import { HowWorkerGridWorks } from "../components/HowWorkerGridWorks";
import { ReportView } from "./ReportView";
import { Clock, FileText, RefreshCw, Layers3, Activity } from "lucide-react";

export function FrictionDashboard({ baseUrl, onSwitchToCore }) {
  const [activeRunId, setActiveRunId] = useState(null);
  const [activeStatus, setActiveStatus] = useState(null);
  const [activeReport, setActiveReport] = useState(null);
  const [runsList, setRunsList] = useState([]);
  const [reposList, setReposList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const pollTimerRef = useRef(null);

  // Fetch recent runs & repos
  const fetchOverview = useCallback(async () => {
    try {
      const [runsRes, reposRes] = await Promise.all([
        frictionApi.listAnalyses(baseUrl),
        frictionApi.listRepositories(baseUrl),
      ]);
      setRunsList(runsRes.items || []);
      setReposList(reposRes.items || []);
    } catch (err) {
      console.error("Failed to load overview:", err);
    }
  }, [baseUrl]);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        const [runsRes, reposRes] = await Promise.all([
          frictionApi.listAnalyses(baseUrl),
          frictionApi.listRepositories(baseUrl),
        ]);
        if (isMounted) {
          setRunsList(runsRes.items || []);
          setReposList(reposRes.items || []);
        }
      } catch (err) {
        console.error("Failed to load overview:", err);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [baseUrl]);

  // Poll status for active run
  useEffect(() => {
    if (!activeRunId || activeStatus?.status === "COMPLETED" || activeStatus?.status === "FAILED") {
      return;
    }

    let isMounted = true;
    async function poll() {
      try {
        const status = await frictionApi.getAnalysisStatus(baseUrl, activeRunId);
        if (!isMounted) return;
        setActiveStatus(status);

        if (status.status === "COMPLETED") {
          const report = await frictionApi.getReport(baseUrl, activeRunId);
          if (isMounted) setActiveReport(report);
          fetchOverview();
        } else if (status.status === "FAILED") {
          fetchOverview();
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }

    pollTimerRef.current = setInterval(poll, 2000);
    return () => {
      isMounted = false;
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [activeRunId, activeStatus?.status, baseUrl, fetchOverview]);

  async function handleStartAnalysis(payload) {
    setLoading(true);
    setError(null);
    setActiveReport(null);
    try {
      const res = await frictionApi.startAnalysis(baseUrl, payload);
      setActiveRunId(res.run_id);
      setActiveStatus({
        run_id: res.run_id,
        repository: res.repository,
        status: "PENDING",
        progress_pct: 10,
        current_stage: "Initializing Run",
      });
      fetchOverview();
    } catch (err) {
      setError(err.message || "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectRun(runId) {
    setActiveRunId(runId);
    setLoading(true);
    try {
      const status = await frictionApi.getAnalysisStatus(baseUrl, runId);
      setActiveStatus(status);
      if (status.status === "COMPLETED") {
        const report = await frictionApi.getReport(baseUrl, runId);
        setActiveReport(report);
      } else {
        setActiveReport(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="friction-dashboard-shell">
      {error && <div className="error-box">{error}</div>}

      <div className="friction-card powered-by-banner">
        <div className="powered-by-header">
          <div className="powered-by-title-wrap">
            <Layers3 size={18} className="text-blue" />
            <div>
              <h3 className="powered-by-title">POWERED BY WORKERGRID PLATFORM</h3>
              <div className="subtle">Project Friction executes 4-stage DAG workloads on distributed WorkerGrid priority queues & background workers.</div>
            </div>
          </div>
          {onSwitchToCore && (
            <button className="primary-button flex-btn" onClick={onSwitchToCore} title="View WorkerGrid Core Execution Details">
              <Activity size={13} />
              <span>View WorkerGrid Execution</span>
            </button>
          )}
        </div>
      </div>

      <HowWorkerGridWorks defaultOpen={false} />


      {activeReport ? (
        <ReportView
          report={activeReport}
          onBack={() => {
            setActiveReport(null);
            setActiveRunId(null);
            setActiveStatus(null);
          }}
          onRefresh={() => handleSelectRun(activeRunId)}
        />
      ) : (
        <>
          <RepositorySelector
            onStart={handleStartAnalysis}
            loading={loading}
            recentRepos={reposList}
          />

          {activeStatus && <AnalysisProgress status={activeStatus} />}

          <div className="friction-card">
            <div className="friction-card-title">
              <Clock size={15} />
              <span>ANALYSIS EXECUTION HISTORY</span>
              <button className="ghost-button icon-btn right-btn" onClick={fetchOverview}>
                <RefreshCw size={13} />
              </button>
            </div>

            {runsList.length === 0 ? (
              <div className="empty">No analysis runs recorded yet. Start one above!</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>REPOSITORY</th>
                      <th>STATUS</th>
                      <th>PROGRESS</th>
                      <th>FRICTION SCORE</th>
                      <th>STAGE</th>
                      <th>CREATED</th>
                      <th>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runsList.map((r) => (
                      <tr key={r.run_id} className={r.run_id === activeRunId ? "row-selected" : ""}>
                        <td>
                          <strong className="mono">{r.repository}</strong>
                          <div className="subtle mono">{r.run_id}</div>
                        </td>
                        <td>
                          <span
                            className={`status-badge ${
                              r.status === "COMPLETED"
                                ? "success"
                                : r.status === "FAILED"
                                ? "danger"
                                : "active"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="mono">{r.progress_pct}%</td>
                        <td>
                          {r.friction_level === "INSUFFICIENT_DATA" ? (
                            <span className="score-chip medium">N/A (INSUFFICIENT DATA)</span>
                          ) : r.overall_friction_score != null ? (
                            <span className={`score-chip ${r.friction_level?.toLowerCase()}`}>
                              {r.overall_friction_score} / 100 ({r.friction_level})
                            </span>
                          ) : (
                            <span className="subtle">—</span>
                          )}
                        </td>
                        <td className="subtle">{r.current_stage}</td>
                        <td className="subtle">{new Date(r.created_at).toLocaleString()}</td>
                        <td>
                          <button
                            className="secondary-button"
                            onClick={() => handleSelectRun(r.run_id)}
                          >
                            <FileText size={12} />
                            <span>View</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
