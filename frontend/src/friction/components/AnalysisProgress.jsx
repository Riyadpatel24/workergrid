import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

export function AnalysisProgress({ status }) {
  if (!status) return null;

  const isComplete = status.status === "COMPLETED";
  const isFailed = status.status === "FAILED";

  return (
    <div className={`friction-card progress-card ${isFailed ? "failed" : isComplete ? "completed" : "active"}`}>
      <div className="progress-header">
        <div className="progress-title">
          {isComplete ? (
            <CheckCircle2 size={18} className="text-green" />
          ) : isFailed ? (
            <AlertCircle size={18} className="text-red" />
          ) : (
            <Loader2 size={18} className="text-blue spin" />
          )}
          <div>
            <strong>{status.repository}</strong>
            <div className="subtle">Run ID: {status.run_id}</div>
          </div>
        </div>
        <div className="progress-badge">
          <span className={`status-badge ${isComplete ? "success" : isFailed ? "danger" : "active"}`}>
            {status.status}
          </span>
        </div>
      </div>

      <div className="progress-track-wrap">
        <div className="progress-info">
          <span>{status.current_stage || "Processing"}</span>
          <strong>{status.progress_pct}%</strong>
        </div>
        <div className="progress-track">
          <div
            className={`progress-fill ${isFailed ? "fill-red" : isComplete ? "fill-green" : "fill-blue"}`}
            style={{ width: `${status.progress_pct}%` }}
          />
        </div>
      </div>

      {status.error_message && (
        <div className="error-box">
          <AlertCircle size={14} />
          <span>{status.error_message}</span>
        </div>
      )}
    </div>
  );
}
