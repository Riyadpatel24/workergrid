import { useState } from "react";
import { FrictionScorecard } from "../components/FrictionScorecard";
import { IndicatorCard } from "../components/IndicatorCard";
import { EvidenceModal } from "../components/EvidenceModal";
import { MetricsChart } from "../components/MetricsChart";
import { ArrowLeft, RefreshCw } from "lucide-react";

export function ReportView({ report, onBack, onRefresh }) {
  const [selectedIndicator, setSelectedIndicator] = useState(null);

  if (!report) return null;

  const indicators = report.indicators || [];
  const metrics = report.metrics || [];

  return (
    <div className="report-view">
      <div className="report-topbar">
        <button className="secondary-button back-btn" onClick={onBack}>
          <ArrowLeft size={14} />
          <span>Back to Analyses</span>
        </button>
        <div className="report-title-meta">
          <h3>{report.repository}</h3>
          <span className="subtle">Run ID: {report.run_id} · Scope: {report.time_window_days} days</span>
        </div>
        <button className="ghost-button icon-btn" onClick={onRefresh} title="Refresh Report">
          <RefreshCw size={14} />
        </button>
      </div>

      <FrictionScorecard report={report} />

      <div className="report-section">
        <h4 className="section-title">FRICTION INDICATORS & ACTIONABLE INSIGHTS</h4>
        <div className="indicators-grid">
          {indicators.map((ind) => (
            <IndicatorCard
              key={ind.id}
              indicator={ind}
              onSelectEvidence={(i) => setSelectedIndicator(i)}
            />
          ))}
        </div>
      </div>

      <MetricsChart metrics={metrics} />

      {selectedIndicator && (
        <EvidenceModal
          indicator={selectedIndicator}
          onClose={() => setSelectedIndicator(null)}
        />
      )}
    </div>
  );
}
