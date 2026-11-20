"""One owner-confirmed, pinned GitHub Actions execution; never executes model code locally.

The profile is deliberately immutable. Clipboard text supplies no command arguments,
workflow names, credentials, paths, or shell fragments. GitHub CLI handles auth in
its pre-existing credential store; the workbench neither reads nor logs the token.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from time import sleep

from .draft_documents import DraftError, _repo_root


REPO = "hibi89/REQ-Evidence-Auditor-A-"
BRANCH = "integration/reqea-p1-20261118"
WORKFLOW = "reqea-audit.yml"
WORKFLOW_BLOB = "fc98f672173926b0364b472235d7ba1593a1efeb"
REQUIREMENTS = "docs/FINAL_BLUEPRINT.md"
_TEST_ID = "REQEA-P2-E-MANUAL-CLI-AUDIT-SMOKE"
_SHA = re.compile(r"[0-9a-f]{40}\Z")


class ExecutionHold(DraftError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def eligible_profile(repository: str, branch: str, revision: str, title: str) -> bool:
    """The manual workflow is the only currently approved external run profile."""
    return (repository == REPO and branch == BRANCH and bool(_SHA.fullmatch(revision))
            and title.startswith("P2-E.") and "GitHub Actions" in title)


def _gh_path() -> str:
    # On Windows use the exact installed, non-PATH-controlled GitHub CLI location.
    candidate = (r"C:\Program Files\GitHub CLI\gh.exe" if os.name == "nt"
                 else shutil.which("gh"))
    if not candidate or not Path(candidate).is_file():
        raise ExecutionHold("HOLD_GH_AUTH_UNAVAILABLE")
    return candidate


def _gh_api(endpoint: str, *, fields: tuple[str, ...] = (), method: str = "GET") -> dict | None:
    if (not endpoint.startswith(f"repos/{REPO}/") or ".." in endpoint or "#" in endpoint
        or method not in ("GET", "POST") or any("\x00" in arg for arg in fields)):
        raise ExecutionHold("HOLD_REQUEST_SCOPE")
    exe = _gh_path()
    args = [exe, "api", "--hostname", "github.com", "--method", method,
            "-H", "Accept: application/vnd.github+json", endpoint]
    for entry in fields:
        args.extend(("-f", entry))
    try:
        result = subprocess.run(args, cwd=str(Path(exe).parent),
                                stdin=subprocess.DEVNULL, capture_output=True,
                                shell=False, check=False, timeout=25,
                                env={**os.environ, "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1",
                                     "GH_PAGER": "", "NO_COLOR": "1"},
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        raise ExecutionHold("HOLD_GH_TRANSPORT") from None
    if result.returncode != 0 or len(result.stdout) > 500_000:
        # Do not expose gh stderr: it may include credential or source details.
        raise ExecutionHold("HOLD_GH_API_OR_PERMISSION")
    if method == "POST":
        # POST /dispatches returns 204 with no run id; never invent one.
        if result.stdout.strip():
            raise ExecutionHold("HOLD_DISPATCH_RESPONSE")
        return None
    try:
        obj = json.loads(result.stdout)
    except (UnicodeError, ValueError):
        raise ExecutionHold("HOLD_GH_RESPONSE") from None
    if not isinstance(obj, dict):
        raise ExecutionHold("HOLD_GH_RESPONSE")
    return obj


def _read_branch_head() -> str:
    doc = _gh_api(f"repos/{REPO}/commits/{BRANCH}")
    sha = doc.get("sha") if doc else None
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ExecutionHold("HOLD_SOURCE_SHA")
    return sha


def _verify_workflow_blob() -> None:
    document = _gh_api(f"repos/{REPO}/contents/.github/workflows/{WORKFLOW}?ref=main")
    if not document or document.get("sha") != WORKFLOW_BLOB:
        raise ExecutionHold("HOLD_WORKFLOW_CHANGED")


def _parse_github_time(raw: object) -> datetime | None:
    if type(raw) is not str:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _find_run(source_sha: str, dispatch_at: datetime) -> list[dict]:
    query = (f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs"
             f"?event=workflow_dispatch&branch={BRANCH}&per_page=30")
    response = _gh_api(query)
    records = response.get("workflow_runs") if response else None
    if not isinstance(records, list):
        raise ExecutionHold("HOLD_RUN_QUERY")
    candidates = []
    for run in records:
        if not isinstance(run, dict):
            continue
        when = _parse_github_time(run.get("created_at"))
        if (run.get("head_sha") != source_sha or run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != BRANCH or type(run.get("id")) is not int
            or not when or not dispatch_at - timedelta(seconds=10) <= when <= dispatch_at + timedelta(minutes=10)):
            continue
        candidates.append(run)
    return candidates


def _public_receipt(record: dict, source_sha: str, *, run_id: int | None = None) -> dict:
    conclusion = record.get("conclusion")
    status = record.get("status")
    if status != "completed":
        state = "RUNNING" if status in ("queued", "in_progress", "waiting", "pending") else "HOLD"
    else:
        state = "PASS" if conclusion == "success" else "FAIL" if conclusion in (
            "failure", "timed_out", "cancelled", "action_required") else "HOLD"
    rid = run_id or record["id"]
    return {"state": state, "test_id": _TEST_ID, "run_id": rid,
            "source_sha": source_sha, "workflow": WORKFLOW,
            "url": f"https://github.com/{REPO}/actions/runs/{rid}",
            "conclusion": conclusion, "started_at": record.get("run_started_at"),
            "finished_at": record.get("updated_at") if status == "completed" else None,
            "exit_code": None, "independent_verified": False,
            "p2_gate_accepted": False,
            "scope": "Actual remote CLI audit smoke only; not P2-A test suite or full P2 gate"}


def execute_once(source_sha: str, notify, *, poll_interval: float = 5,
                 max_polls: int = 60) -> None:
    """Dispatch once, then reconcile one uniquely identified run.

    notify persists an INTENT before this function is called; no retry after a
    dispatch error or restart. This prevents ambiguous duplicate side effects.
    """
    try:
        if not _SHA.fullmatch(source_sha):
            raise ExecutionHold("HOLD_SOURCE_SHA")
        if _read_branch_head() != source_sha:
            raise ExecutionHold("HOLD_SOURCE_MOVED")
        _verify_workflow_blob()
        # A final comparison immediately before dispatch limits branch race.
        if _read_branch_head() != source_sha:
            raise ExecutionHold("HOLD_SOURCE_MOVED")
        at = datetime.now(timezone.utc)
        notify({"state": "DISPATCHING", "dispatched_at": at.isoformat()})
        _gh_api(f"repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches", method="POST",
                fields=(f"ref={BRANCH}", f"inputs[requirements]={REQUIREMENTS}"))
        notify({"state": "RUNNING", "dispatched_at": at.isoformat()})
        run_id = None
        for _ in range(max_polls):
            candidates = _find_run(source_sha, at)
            if len(candidates) > 1:
                raise ExecutionHold("HOLD_AMBIGUOUS_RUN_ID")
            if len(candidates) == 1:
                found = candidates[0]
                if run_id is not None and found["id"] != run_id:
                    raise ExecutionHold("HOLD_RUN_CHANGED")
                run_id = found["id"]
                outcome = _public_receipt(found, source_sha, run_id=run_id)
                notify(outcome)
                if outcome["state"] != "RUNNING":
                    return
            sleep(poll_interval)
        raise ExecutionHold("HOLD_RUN_TIMEOUT_NO_REDISPATCH")
    except ExecutionHold as exc:
        notify({"state": "HOLD", "code": exc.code, "p2_gate_accepted": False,
                "independent_verified": False})


def reconcile_existing(source_sha: str, receipt: dict) -> dict:
    """Read one previously dispatched fixed workflow; never dispatch or retry.

    After a crash, a saved intent with no dispatched_at is NOT evidence of a
    dispatched run. With no run ID, require one unique matching workflow run.
    """
    if (type(receipt) is not dict or not _SHA.fullmatch(source_sha)
        or receipt.get("source_sha") != source_sha
        or receipt.get("test_id") != _TEST_ID or receipt.get("workflow") != WORKFLOW):
        raise ExecutionHold("HOLD_RECONCILE_SCOPE")
    run_id = receipt.get("run_id")
    at = _parse_github_time(receipt.get("dispatched_at"))
    if run_id is None:
        if at is None:
            raise ExecutionHold("HOLD_NO_DISPATCH_EVIDENCE")
        candidates = _find_run(source_sha, at)
        if len(candidates) != 1:
            raise ExecutionHold("HOLD_AMBIGUOUS_RUN_ID" if candidates else "HOLD_RUN_NOT_FOUND")
        record = candidates[0]
        run_id = record["id"]
    else:
        if type(run_id) is not int or not 0 < run_id < (1 << 63):
            raise ExecutionHold("HOLD_RUN_ID_INVALID")
        record = _gh_api(f"repos/{REPO}/actions/runs/{run_id}")
        if not record or record.get("id") != run_id:
            raise ExecutionHold("HOLD_RUN_NOT_FOUND")
        path = record.get("path")
        expected = f".github/workflows/{WORKFLOW}@refs/heads/main"
        if type(path) is not str or path not in (expected, f"{REPO}/{expected}"):
            raise ExecutionHold("HOLD_WORKFLOW_MISMATCH")
        if at is not None:
            created = _parse_github_time(record.get("created_at"))
            if created is None or not at - timedelta(seconds=10) <= created <= at + timedelta(minutes=10):
                raise ExecutionHold("HOLD_RUN_TIME_MISMATCH")
    if (record.get("head_sha") != source_sha or record.get("head_branch") != BRANCH
        or record.get("event") != "workflow_dispatch" or type(record.get("id")) is not int):
        raise ExecutionHold("HOLD_RUN_IDENTITY_MISMATCH")
    result = _public_receipt(record, source_sha, run_id=run_id)
    if result["state"] == "RUNNING":
        # A one-shot read is not a long-lived background polling worker.
        result.update(state="HOLD", code="HOLD_REMOTE_STILL_RUNNING_RECHECK_LATER",
                      remote_state="RUNNING")
    elif result["state"] == "HOLD":
        result["code"] = "HOLD_REMOTE_STATUS_UNKNOWN"
    return result


def initial_receipt(source_sha: str) -> dict:
    return {"state": "INTENT_RECORDED", "source_sha": source_sha,
            "test_id": _TEST_ID, "workflow": WORKFLOW, "requirements": REQUIREMENTS,
            "run_id": None, "exit_code": None, "independent_verified": False,
            "p2_gate_accepted": False}
