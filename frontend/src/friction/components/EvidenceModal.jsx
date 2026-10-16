import { X, ExternalLink, GitPullRequest, Workflow, AlertCircle } from "lucide-react";

export function EvidenceModal({ indicator, onClose }) {
  if (!indicator) return null;

  const evidence = indicator.evidence || [];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="eyebrow">EVIDENCE INSPECTION</div>
            <h3>{indicator.title}</h3>
          </div>
          <button className="ghost-button icon-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          <p className="subtle-text">{indicator.summary}</p>
          <div className="evidence-list">
            {evidence.length === 0 ? (
              <div className="empty">No specific evidence links recorded.</div>
            ) : (
              evidence.map((ev) => (
                <div className="evidence-row" key={ev.id}>
                  <div className="evidence-icon">
                    {ev.entity_type === "pull_request" ? (
                      <GitPullRequest size={16} />
                    ) : ev.entity_type === "workflow_run" ? (
                      <Workflow size={16} />
                    ) : (
                      <AlertCircle size={16} />
                    )}
                  </div>
                  <div className="evidence-main">
                    <div className="evidence-title">
                      <strong>{ev.external_id}</strong>: {ev.title}
                    </div>
                    {ev.metrics_breakdown && (
                      <div className="evidence-breakdown mono">
                        {Object.entries(ev.metrics_breakdown).map(([k, v]) => (
                          <span key={k} className="chip">
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  {ev.url && (
                    <a
                      href={ev.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="secondary-button link-btn"
                    >
                      <span>Open GitHub</span>
                      <ExternalLink size={12} />
                    </a>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
        <div className="modal-footer">
          <button className="secondary-button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
