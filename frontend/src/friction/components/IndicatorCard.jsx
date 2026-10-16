import { AlertTriangle, Info, ArrowRight, HelpCircle } from "lucide-react";

export function IndicatorCard({ indicator, onSelectEvidence }) {
  const sev = (indicator.severity || "LOW").toUpperCase();
  const isInsufficient = sev === "INSUFFICIENT_DATA";

  const tone = isInsufficient
    ? "warning"
    : sev === "CRITICAL"
    ? "danger"
    : sev === "HIGH"
    ? "warning"
    : "info";

  return (
    <div className={`indicator-card ${tone}`}>
      <div className="indicator-header">
        <div className="indicator-title-wrap">
          {isInsufficient ? (
            <HelpCircle size={17} className="indicator-icon text-yellow" />
          ) : sev === "CRITICAL" || sev === "HIGH" ? (
            <AlertTriangle size={17} className="indicator-icon" />
          ) : (
            <Info size={17} className="indicator-icon" />
          )}
          <h4>{indicator.title}</h4>
        </div>
        <span className={`severity-badge ${tone}`}>
          {isInsufficient ? "INSUFFICIENT DATA" : sev}
        </span>
      </div>

      <p className="indicator-summary">{indicator.summary}</p>

      {indicator.recommendation && (
        <div className="recommendation-box">
          <strong>Recommended Action:</strong>
          <p>{indicator.recommendation}</p>
        </div>
      )}

      {indicator.evidence && indicator.evidence.length > 0 && (
        <div className="indicator-footer">
          <span className="subtle">{indicator.evidence.length} evidence item(s)</span>
          <button
            type="button"
            className="ghost-button evidence-btn"
            onClick={() => onSelectEvidence(indicator)}
          >
            <span>Inspect Evidence</span>
            <ArrowRight size={13} />
          </button>
        </div>
      )}
    </div>
  );
}
