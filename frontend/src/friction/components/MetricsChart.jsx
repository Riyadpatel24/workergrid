import { BarChart3 } from "lucide-react";

export function MetricsChart({ metrics }) {
  if (!metrics || metrics.length === 0) return null;

  return (
    <div className="friction-card">
      <div className="friction-card-title">
        <BarChart3 size={15} />
        <span>CALCULATED METRIC INDICATORS</span>
      </div>
      <div className="metrics-list-grid">
        {metrics.map((m) => (
          <div className="metric-detail-item" key={m.name}>
            <div className="metric-header-row">
              <span className="metric-category-chip">{m.category}</span>
              <strong className="metric-val">
                {m.value} {m.unit || ""}
              </strong>
            </div>
            <div className="metric-name-text">{formatMetricName(m.name)}</div>
            {m.details && (
              <div className="metric-details-meta mono">
                {Object.entries(m.details).map(([k, v]) => (
                  <span key={k}>
                    {k}: {v}{" "}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatMetricName(name) {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
}
