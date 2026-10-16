from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """Abstract interface for VCS / issue tracker data collectors."""

    @abstractmethod
    def fetch_repository_info(self, owner: str, repo: str) -> dict[str, Any]:
        """Fetch general metadata for the repository."""
        pass

    @abstractmethod
    def fetch_pull_requests(self, owner: str, repo: str, days: int) -> list[dict[str, Any]]:
        """Fetch pull requests opened/merged/updated within the specified days window."""
        pass

    @abstractmethod
    def fetch_ci_runs(self, owner: str, repo: str, days: int) -> list[dict[str, Any]]:
        """Fetch CI workflow runs within the specified days window."""
        pass

    @abstractmethod
    def fetch_issues(self, owner: str, repo: str, days: int) -> list[dict[str, Any]]:
        """Fetch issues opened/closed/updated within the specified days window."""
        pass
