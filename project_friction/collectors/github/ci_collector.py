from datetime import datetime, timedelta, timezone
from typing import Any
from project_friction.collectors.github.client import GitHubClient, RateLimitExceededError


class GitHubCICollector:
    def __init__(self, client: GitHubClient):
        self.client = client

    def fetch_ci_runs(self, owner: str, repo: str, days: int = 30, max_items: int = 50) -> list[dict[str, Any]]:
        runs = []
        endpoint = f"repos/{owner}/{repo}/actions/runs"
        params = {
            "per_page": min(50, max_items),
        }
        try:
            data, _ = self.client.get(endpoint, params)
            workflow_runs = data.get("workflow_runs", []) if isinstance(data, dict) else []

            since_date = datetime.now(timezone.utc) - timedelta(days=days)

            for run in workflow_runs:
                created_at_str = run.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if created_at < since_date:
                        continue

                runs.append({
                    "id": run.get("id"),
                    "name": run.get("name", "Workflow"),
                    "event": run.get("event"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "created_at": run.get("created_at"),
                    "updated_at": run.get("updated_at"),
                    "html_url": run.get("html_url", f"https://github.com/{owner}/{repo}/actions/runs/{run.get('id')}"),
                    "run_number": run.get("run_number"),
                    "head_branch": run.get("head_branch"),
                })
                if len(runs) >= max_items:
                    break
        except RateLimitExceededError:
            raise
        except Exception as err:
            print(f"[CICollector] Error fetching CI runs: {err}")
            raise

        return runs

