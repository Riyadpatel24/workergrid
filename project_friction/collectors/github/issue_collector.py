from datetime import datetime, timedelta, timezone
from typing import Any
from project_friction.collectors.github.client import GitHubClient, RateLimitExceededError


class GitHubIssueCollector:
    def __init__(self, client: GitHubClient):
        self.client = client

    def fetch_issues(self, owner: str, repo: str, days: int = 30, max_items: int = 50) -> list[dict[str, Any]]:
        issues = []
        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        since_formatted = since_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        endpoint = f"repos/{owner}/{repo}/issues"
        params = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "since": since_formatted,
            "per_page": min(50, max_items),
        }
        try:
            data, _ = self.client.get(endpoint, params)
            if isinstance(data, list):
                for item in data:
                    # Filter out PRs (GitHub issues API includes PRs)
                    if "pull_request" in item:
                        continue

                    issues.append({
                        "number": item.get("number"),
                        "title": item.get("title", ""),
                        "state": item.get("state", ""),
                        "created_at": item.get("created_at"),
                        "closed_at": item.get("closed_at"),
                        "updated_at": item.get("updated_at"),
                        "comments_count": item.get("comments", 0),
                        "user_login": item.get("user", {}).get("login", "unknown"),
                        "html_url": item.get("html_url", f"https://github.com/{owner}/{repo}/issues/{item.get('number')}"),
                    })
                    if len(issues) >= max_items:
                        break
        except RateLimitExceededError:
            raise
        except Exception as err:
            print(f"[IssueCollector] Error fetching issues: {err}")
            raise

        return issues

