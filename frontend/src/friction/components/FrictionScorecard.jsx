import { GitPullRequest, ShieldAlert, Clock, Zap, AlertCircle } from "lucide-react";

export function FrictionScorecard({ report }) {
  if (!report) return null;

  const level = report.friction_level || "UNKNOWN";
  const isInsufficient = level === "INSUFFICIENT_DATA" || report.overall_friction_score == null;
  const score = isInsufficient ? "N/A" : report.overall_friction_score;

  const tone = isInsufficient
    ? "warning"
    : level === "LOW"
    ? "success"
    : level === "MEDIUM"
    ? "warning"
    : "danger";

  const titleText = isInsufficient ? "INSUFFICIENT ACTIVITY" : `${level} FRICTION`;

  const desc = isInsufficient
    ? "No PR, CI, or issue activity was found in the selected period. Run the analysis over a longer period for meaningful friction metrics."
    : level === "LOW"
    ? "Smooth developer workflow with minimal review or CI delays."
    : level === "MEDIUM"
    ? "Moderate friction points identified in review cycles or staleness."
    : level === "HIGH"
    ? "Significant workflow bottlenecks slowing delivery velocity."
    : "Critical friction blockers severely delaying deployment throughput.";

  const dimensions = report.dimensions || {};

  return (
    <div className="scorecard-container">
      <div className={`scorecard-hero ${tone}`}>
        <div className="gauge-wrap">
          {isInsufficient ? (
            <AlertCircle size={28} className="text-yellow" />
          ) : (
            <>
              <div className="score-number">{score}</div>
              <div className="score-max">/ 100</div>
            </>
          )}
        </div>
        <div className="score-details">
          <div className="eyebrow">FRICTION SCORE INDEX</div>
          <h2>{titleText}</h2>
          <p>{desc}</p>
        </div>
      </div>

      <div className="dimensions-grid">
        <DimensionCard
          icon={GitPullRequest}
          title="Code Review Friction"
          score={isInsufficient ? null : dimensions.code_review}
          caption="Latency to first review"
        />
        <DimensionCard
          icon={ShieldAlert}
          title="CI/CD Stability"
          score={isInsufficient ? null : dimensions.ci_cd}
          caption="Workflow build failure rate"
        />
        <DimensionCard
          icon={Clock}
          title="Backlog Staleness"
          score={isInsufficient ? null : dimensions.backlog_staleness}
          caption="Inactive PRs & open issues"
        />
        <DimensionCard
          icon={Zap}
          title="Delivery Velocity"
          score={isInsufficient ? null : dimensions.delivery_velocity}
          caption="Lead time created -> merged"
        />
      </div>
    </div>
  );
}

function DimensionCard({ icon: Icon, title, score, caption }) {
  const isNa = score == null;
  const tone = isNa ? "neutral" : score <= 30 ? "good" : score <= 60 ? "warn" : "bad";
  return (
    <div className={`dimension-card ${tone}`}>
      <div className="dim-head">
        <Icon size={16} />
        <span>{title}</span>
      </div>
      <div className="dim-value">{isNa ? "N/A" : score}</div>
      <div className="dim-caption">{caption}</div>
    </div>
  );
}
