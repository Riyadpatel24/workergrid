from typing import Any
from sqlalchemy.orm import Session
from app.core.security import decrypt_token
from app.core.time import utcnow_naive
from app.models.friction import FrictionAnalysisRun, FrictionRawSnapshot, Repository
from app.models.user import UserGitHubAccount
from project_friction.collectors.github import (
    GitHubCICollector,
    GitHubClient,
    GitHubIssueCollector,
    GitHubPRCollector,
)


def handle_friction_init(db: Session, payload: dict[str, Any]):
    run_id = payload["run_id"]
    owner = payload["owner"]
    name = payload["name"]
    user_id = payload.get("user_id")
    full_name = f"{owner}/{name}".lower()

    # Ensure Repository DB record exists (scoped to user_id if present)
    repo_query = db.query(Repository).filter(Repository.full_name == full_name)
    if user_id:
        repo_query = repo_query.filter(Repository.user_id == user_id)
    repo = repo_query.first()

    if not repo:
        repo = Repository(user_id=user_id, owner=owner, name=name, full_name=full_name, default_branch="main")
        db.add(repo)
        db.commit()
        db.refresh(repo)

    # Ensure FrictionAnalysisRun DB record exists
    run = db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id).first()
    if not run:
        run = FrictionAnalysisRun(
            id=run_id,
            user_id=user_id,
            repository_id=repo.id,
            status="COLLECTING",
            time_window_days=payload.get("time_window_days", 30),
            started_at=utcnow_naive(),
        )
        db.add(run)
    else:
        if user_id and not run.user_id:
            run.user_id = user_id
        run.status = "COLLECTING"
        run.started_at = utcnow_naive()

    db.commit()
    print(f"[TaskHandler] friction_init completed for run {run_id}")


def handle_friction_collect_github(db: Session, payload: dict[str, Any]):
    run_id = payload["run_id"]
    owner = payload["owner"]
    name = payload["name"]
    days = payload.get("time_window_days", 30)
    token = payload.get("github_token")
    user_id = payload.get("user_id")

    run_record = db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id).first()
    if run_record and not user_id:
        user_id = run_record.user_id

    # If explicit token not provided, attempt to decrypt user's stored OAuth token
    if not token and user_id:
        gh_account = db.query(UserGitHubAccount).filter(UserGitHubAccount.user_id == user_id).first()
        if gh_account and gh_account.encrypted_access_token:
            try:
                token = decrypt_token(gh_account.encrypted_access_token)
            except Exception as err:
                print(f"[TaskHandler] Warning: Failed to decrypt GitHub token for user_id={user_id}: {err}")

    client = GitHubClient(token=token)
    pr_collector = GitHubPRCollector(client)
    ci_collector = GitHubCICollector(client)
    issue_collector = GitHubIssueCollector(client)

    print(f"[TaskHandler] Collecting GitHub data for {owner}/{name} (last {days} days)...")

    prs = []
    ci_runs = []
    issues = []
    collector_errors = []

    # Fetch PRs
    try:
        prs = pr_collector.fetch_pull_requests(owner, name, days=days, max_items=50)
        for pr in prs:
            snap = FrictionRawSnapshot(
                user_id=user_id,
                run_id=run_id,
                entity_type="pull_request",
                external_id=str(pr["number"]),
                snapshot_data=pr,
            )
            db.add(snap)
    except Exception as err:
        print(f"[TaskHandler] PRCollector failed for {owner}/{name}: {err}")
        collector_errors.append(f"PRCollector: {err}")

    # Fetch CI Workflow Runs
    try:
        ci_runs = ci_collector.fetch_ci_runs(owner, name, days=days, max_items=50)
        for run in ci_runs:
            snap = FrictionRawSnapshot(
                user_id=user_id,
                run_id=run_id,
                entity_type="workflow_run",
                external_id=str(run["id"]),
                snapshot_data=run,
            )
            db.add(snap)
    except Exception as err:
        print(f"[TaskHandler] CICollector failed for {owner}/{name}: {err}")
        collector_errors.append(f"CICollector: {err}")

    # Fetch Issues
    try:
        issues = issue_collector.fetch_issues(owner, name, days=days, max_items=50)
        for issue in issues:
            snap = FrictionRawSnapshot(
                user_id=user_id,
                run_id=run_id,
                entity_type="issue",
                external_id=str(issue["number"]),
                snapshot_data=issue,
            )
            db.add(snap)
    except Exception as err:
        print(f"[TaskHandler] IssueCollector failed for {owner}/{name}: {err}")
        collector_errors.append(f"IssueCollector: {err}")


    run_record = db.query(FrictionAnalysisRun).filter(FrictionAnalysisRun.id == run_id).first()

    if collector_errors and len(prs) == 0 and len(ci_runs) == 0 and len(issues) == 0:
        err_detail = "; ".join(collector_errors)
        if run_record:
            run_record.status = "FAILED"
            run_record.error_message = f"GitHub API collection failed: {err_detail}"
        db.commit()
        raise RuntimeError(f"GitHub API collection failed for {owner}/{name}: {err_detail}")

    if run_record:
        run_record.status = "CALCULATING"

    db.commit()
    print(f"[TaskHandler] friction_collect_github completed for run {run_id} ({len(prs)} PRs, {len(ci_runs)} CI, {len(issues)} Issues)")

