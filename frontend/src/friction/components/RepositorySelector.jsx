import { useState } from "react";
import { Play, Calendar, GitFork } from "lucide-react";

export function RepositorySelector({ onStart, loading, recentRepos }) {
  const [repoInput, setRepoInput] = useState("");
  const [days, setDays] = useState(30);
  const [token, setToken] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    const parts = repoInput.trim().split("/");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      alert("Please enter a valid owner/repository string (e.g. facebook/react)");
      return;
    }
    onStart({
      owner: parts[0],
      name: parts[1],
      time_window_days: Number(days),
      github_token: token.trim() || undefined,
    });
  }

  function handleSelectRecent(full_name) {
    setRepoInput(full_name);
  }

  return (
    <div className="friction-card">
      <div className="friction-card-title">
        <GitFork size={16} />
        <span>START NEW FRICTION ANALYSIS</span>
      </div>
      <form onSubmit={handleSubmit} className="selector-form">
        <div className="form-group flex-2">
          <label>GitHub Repository (owner/repo)</label>
          <input
            type="text"
            placeholder="e.g. facebook/react or pallets/flask"
            value={repoInput}
            onChange={(e) => setRepoInput(e.target.value)}
            required
          />
        </div>
        <div className="form-group flex-1">
          <label>Scope (Days)</label>
          <div className="select-wrap">
            <Calendar size={13} className="select-icon" />
            <select value={days} onChange={(e) => setDays(e.target.value)}>
              <option value={7}>Last 7 Days</option>
              <option value={30}>Last 30 Days</option>
              <option value={90}>Last 90 Days</option>
            </select>
          </div>
        </div>
        <div className="form-group flex-1">
          <label>
            GitHub PAT <span className="subtle">(Optional)</span>
          </label>
          <input
            type="password"
            placeholder="ghp_..."
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </div>
        <div className="form-group submit-group">
          <button type="submit" className="primary-button run-btn" disabled={loading}>
            <Play size={14} />
            <span>{loading ? "Initializing..." : "Start Analysis"}</span>
          </button>
        </div>
      </form>

      {recentRepos && recentRepos.length > 0 && (
        <div className="recent-repos">
          <span className="subtle">Quick Select:</span>
          {recentRepos.map((r) => (
            <button
              key={r.id}
              type="button"
              className="chip-btn"
              onClick={() => handleSelectRecent(r.full_name)}
            >
              {r.full_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
