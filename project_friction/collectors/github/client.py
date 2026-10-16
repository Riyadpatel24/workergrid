import json
import time
from datetime import datetime, timezone
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


class RateLimitExceededError(Exception):
    def __init__(self, reset_timestamp: int, message: str = "GitHub API rate limit exceeded"):
        super().__init__(message)
        self.reset_timestamp = reset_timestamp


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.token = token

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "WorkerGrid-ProjectFriction/1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token and self.token.strip():
            headers["Authorization"] = f"Bearer {self.token.strip()}"
        return headers

    def get(self, endpoint: str, params: dict | None = None) -> tuple[Any, dict]:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"

        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                headers = dict(response.info())
                remaining = int(headers.get("X-RateLimit-Remaining", 60))
                reset_time = int(headers.get("X-RateLimit-Reset", 0))

                if remaining < 3 and reset_time > 0:
                    now = int(time.time())
                    wait = reset_time - now
                    if 0 < wait <= 30:
                        print(f"[GitHubClient] Rate limit near capacity. Waiting {wait}s...")
                        time.sleep(wait)

                body = response.read().decode("utf-8")
                data = json.loads(body) if body else {}
                return data, headers
        except urllib.error.HTTPError as err:
            remaining = int(err.headers.get("X-RateLimit-Remaining", 0))
            reset_time = int(err.headers.get("X-RateLimit-Reset", 0))

            if err.code in (403, 429) or remaining == 0:
                now = int(time.time())
                wait = max(1, reset_time - now) if reset_time > 0 else 60
                if wait <= 30:
                    print(f"[GitHubClient] Rate limit hit. Pausing {wait}s...")
                    time.sleep(wait)
                    return self.get(endpoint, params)
                raise RateLimitExceededError(reset_time, f"GitHub rate limit exceeded. Reset in {wait} seconds.")
            elif err.code == 404:
                raise ValueError(f"Resource not found: {endpoint}")
            else:
                raise RuntimeError(f"GitHub API HTTP error {err.code}: {err.reason}")
        except Exception as exc:
            raise RuntimeError(f"GitHub API connection failed: {exc}")
