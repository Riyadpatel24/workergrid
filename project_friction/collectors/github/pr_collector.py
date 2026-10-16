from datetime import datetime, timedelta, timezone
from typing import Any
from project_friction.collectors.github.client import GitHubClient, RateLimitExceededError


class GitHubPRCollector:
    def __init__(self, client: GitHubClient):
        self.client = client

    def fetch_pull_requests(
        self,
        owner: str,
        repo: str,
        days: int = 30,
        max_items: int = 50,
        fetch_reviews_max: int = 5,
    ) -> list[dict[str, Any]]:
        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        prs = []
        page = 1
        reviews_fetched = 0

        while len(prs) < max_items and page <= 3:
            endpoint = f"repos/{owner}/{repo}/pulls"
            params = {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": min(30, max_items - len(prs)),
                "page": page,
            }
            try:
                data, _ = self.client.get(endpoint, params)
                if not data or not isinstance(data, list):
                    break

                for item in data:
                    updated_at_str = item.get("updated_at")
                    if updated_at_str:
                        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                        if updated_at < since_date:
                            continue

                    pr_number = item["number"]
                    first_review_at = None
                    if reviews_fetched < fetch_reviews_max:
                        first_review_at = self._fetch_first_review_time(owner, repo, pr_number)
                        reviews_fetched += 1

                    pr_record = {
                        "number": pr_number,
                        "title": item.get("title", ""),
                        "state": item.get("state", ""),
                        "user_login": item.get("user", {}).get("login", "unknown"),
                        "created_at": item.get("created_at"),
                        "merged_at": item.get("merged_at"),
                        "closed_at": item.get("closed_at"),
                        "updated_at": item.get("updated_at"),
                        "draft": item.get("draft", False),
                        "first_review_at": first_review_at,
                        "review_comments_count": item.get("review_comments", 0) + item.get("comments", 0),
                        "html_url": item.get("html_url", f"https://github.com/{owner}/{repo}/pull/{pr_number}"),
                    }
                    prs.append(pr_record)
                    if len(prs) >= max_items:
                        break

                if len(data) < params["per_page"]:
                    break
                page += 1
            except RateLimitExceededError:
                raise
            except Exception as err:
                print(f"[PRCollector] Warning: Error fetching page {page}: {err}")
                if not prs:
                    raise
                break

        return prs

    def _fetch_first_review_time(self, owner: str, repo: str, pr_number: int) -> str | None:
        try:
            endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"
            data, _ = self.client.get(endpoint, {"per_page": 10})
            if isinstance(data, list) and len(data) > 0:
                data.sort(key=lambda r: r.get("submitted_at", ""))
                return data[0].get("submitted_at")
        except Exception as err:
            print(f"[PRCollector] Warning: Failed to fetch reviews for PR #{pr_number}: {err}")
        return None

