"""Zero-VM bounded OpenCode request builder. Generated code execution DENIED.

This module builds inert requests. A formerly injectable sandbox runner entry
is permanently HOLD and cannot invoke any supplied object after owner consent.
The native CPU Pure Player handles only generated *text* without code execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Callable, Protocol

from my_local_ai.contracts.approval import OwnerGrant, authorize_claim
from my_local_ai.contracts.task import TaskSpec, safe_path
from .budgets import BudgetExceeded, BudgetGuard
from .provider_policy import LoopbackEndpoint, require_qwen_model, ProviderHold
from .worker_lock import ModelLockBusy, ModelLockUnsafe, OneModelLock

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_MESSAGE = 16_384
_MAX_OUTPUT = 262_144
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _no_alias_ancestors(path: Path) -> None:
    # resolve() by itself hides a symlinked parent. Attestation still belongs
    # to the independent protected sandbox, not this lexical/host preflight.
    for part in (path.absolute(), *path.absolute().parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE:
            raise ValueError("worktree ancestor is symlink or junction")



class WorkerHold(RuntimeError):
    """Only redacted reason codes; never echo config, prompts or credentials."""

    def __init__(self, code: str):
        self.code = code if code in {
            "NO_ISOLATION", "NO_OWNER_GO", "BAD_CONTRACT", "UNSAFE_WORKTREE",
            "UNSAFE_MODEL", "UNSAFE_PROMPT", "NO_RESOURCE_GUARD",
            "SANDBOX_FAILURE", "UNTRUSTED_OUTPUT", "RESOURCE_LIMIT",
        } else "SANDBOX_FAILURE"
        super().__init__(self.code)


@dataclass(frozen=True)
class PreparedOpenCodeRun:
    task_id: str
    plan_sha256: str
    source_sha: str
    allowed_paths: tuple[str, ...]
    worktree: str
    argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]
    prompt: str
    untrusted: bool = True


@dataclass(frozen=True)
class UntrustedCandidate:
    task_id: str
    response_sha256: str
    declared_paths: tuple[str, ...]
    status: str = "REVIEW_PENDING"
    untrusted: bool = True


class IsolatedOpenCodeRunner(Protocol):
    """Implemented only in a separately protected OS sandbox executor, not guest code."""

    def attest_worktree(self, request: PreparedOpenCodeRun) -> bool: ...
    def invoke(self, request: PreparedOpenCodeRun) -> object: ...


def _v2_config(model: str, allowed_paths: tuple[str, ...]) -> str:
    # Documented OpenCode V2 syntax. A newer/unknown permission engine must
    # be rejected by the isolated launcher rather than silently falling back.
    permissions = [{"action": "*", "resource": "*", "effect": "deny"}]
    for path in allowed_paths:
        permissions.extend((
            {"action": "read", "resource": path, "effect": "allow"},
            {"action": "edit", "resource": path, "effect": "allow"},
        ))
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": "ollama/" + model,
        "permissions": permissions,
        "policies": [
            # In V2, policies are hard-deny rules evaluated *after* saved
            # approvals, agents and inherited config permissions. An allow
            # lifts the hard deny; it never grants permission by itself.
            {"action": "provider.use", "resource": "*", "effect": "deny"},
            {"action": "provider.use", "resource": "ollama", "effect": "allow"},
            {"action": "tool.use", "resource": "*", "effect": "deny"},
            *(
                item
                for path in allowed_paths
                for item in (
                    {"action": "tool.use", "resource": "read:" + path, "effect": "allow"},
                    {"action": "tool.use", "resource": "edit:" + path, "effect": "allow"},
                )
            ),
        ],
        "mcp": {},
        # OpenCode V2 uses plural 'plugins'. The old singular field was
        # ignored and could accidentally load installed plugins.
        "plugins": [],
        "update": "disable",
    }
    return json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def prepare_opencode_run(
    task: TaskSpec, *, plan_sha256: str, source_sha: str,
    disposable_worktree: str, original_checkout: str,
    prompt: str, model: str = "qwen3:4b-instruct",
    ollama_endpoint: str = "http://127.0.0.1:11434",
) -> PreparedOpenCodeRun:
    """Build a non-executing, explicitly scoped launch request.

    This lexical/FS precheck is NOT proof of a disposable Git worktree or of
    symlink-free file contents. The trusted sandbox must attest those invariants.
    """
    if not isinstance(task, TaskSpec) or not isinstance(plan_sha256, str) or not _SHA64.fullmatch(plan_sha256):
        raise WorkerHold("BAD_CONTRACT")
    if (not isinstance(source_sha, str) or not _SHA40.fullmatch(source_sha)
        or task.source_sha != source_sha or task.plan_sha != plan_sha256
        or not task.allowed_paths or len(set(task.allowed_paths)) != len(task.allowed_paths)):
        raise WorkerHold("BAD_CONTRACT")
    try:
        paths = tuple(safe_path(value) for value in task.allowed_paths)
        local_model = require_qwen_model(model)
        endpoint = LoopbackEndpoint.parse(ollama_endpoint)
    except (ValueError, ProviderHold, TypeError):
        raise WorkerHold("UNSAFE_MODEL") from None
    if not isinstance(prompt, str) or not prompt.strip() or "\0" in prompt:
        raise WorkerHold("UNSAFE_PROMPT")
    try:
        if len(prompt.encode("utf-8")) > _MAX_MESSAGE:
            raise WorkerHold("UNSAFE_PROMPT")
    except UnicodeError:
        raise WorkerHold("UNSAFE_PROMPT") from None
    try:
        if not isinstance(disposable_worktree, str) or not isinstance(original_checkout, str):
            raise ValueError("invalid path types")
        worktree, original = Path(disposable_worktree), Path(original_checkout)
        if (not worktree.is_absolute() or not original.is_absolute()
            or ".." in worktree.parts or ".." in original.parts):
            raise ValueError("unsafe lexical worktree path")
        _no_alias_ancestors(worktree)
        _no_alias_ancestors(original)
        if (not worktree.is_absolute() or not original.is_absolute()
            or not worktree.is_dir() or not original.is_dir()
            or worktree.is_symlink() or original.is_symlink()
            or worktree.resolve() == original.resolve()
            or original.resolve() in worktree.resolve().parents
            or worktree.resolve() in original.resolve().parents):
            raise ValueError("unsafe worktree identity")
    except (OSError, ValueError, RuntimeError):
        raise WorkerHold("UNSAFE_WORKTREE") from None

    config = _v2_config(local_model, paths)
    env = (
        ("OLLAMA_HOST", f"http://[{endpoint.host}]:{endpoint.port}" if ":" in endpoint.host else f"http://{endpoint.host}:{endpoint.port}"),
        ("OPENCODE_CONFIG_CONTENT", config),
    )
    # No shell, --auto, server URL, session continuation, plugin, remote API,
    # inherited host environment, or arbitrary argv from a model/task.
    return PreparedOpenCodeRun(
        task_id=task.task_id, plan_sha256=plan_sha256, source_sha=source_sha,
        allowed_paths=paths, worktree=str(worktree.resolve()),
        argv=("opencode", "run", "--standalone", "--archived",
              "--agent", "build", "--model", "ollama/" + local_model,
              "--format", "json", prompt),
        environment=env, prompt=prompt,
    )


def run_in_sandbox(
    prepared: PreparedOpenCodeRun, *, owner_grant: OwnerGrant | None,
    trusted_hmac_key: bytes | None, live_consent_check: Callable[[str, str, str], bool] | None,
    now_seconds: int, sandbox: IsolatedOpenCodeRunner | None,
    model_lock: OneModelLock | None, budget: BudgetGuard | None,
    trusted_task: TaskSpec | None = None,
    trusted_original_checkout: str | None = None,
    trusted_worktree: str | None = None,
    trusted_model: str = "qwen3:4b-instruct",
    trusted_ollama_endpoint: str = "http://127.0.0.1:11434",
) -> UntrustedCandidate:
    """Deprecated execution entry: fail-closed for all V1.3 inputs.

    Only approved fixed Pure Player operations may inspect generated text.
    No owner claim, injected callable or sandbox object can run code.
    """
    if not isinstance(prepared, PreparedOpenCodeRun) or prepared.untrusted is not True:
        raise WorkerHold("BAD_CONTRACT")
    # Reconstruct the exact worker request from trusted Controller inputs. A
    # dataclass is not a capability: an untrusted worker could forge its argv,
    # config, target worktree, task ID or allowed_paths after preparation.
    if (not isinstance(trusted_task, TaskSpec)
        or not isinstance(trusted_original_checkout, str)
        or not isinstance(trusted_worktree, str)):
        raise WorkerHold("BAD_CONTRACT")
    try:
        expected = prepare_opencode_run(
            trusted_task, plan_sha256=trusted_task.plan_sha,
            source_sha=trusted_task.source_sha,
            disposable_worktree=trusted_worktree,
            original_checkout=trusted_original_checkout,
            prompt=prepared.prompt, model=trusted_model,
            ollama_endpoint=trusted_ollama_endpoint,
        )
    except (WorkerHold, TypeError, ValueError):
        raise WorkerHold("BAD_CONTRACT") from None
    if prepared != expected:
        raise WorkerHold("BAD_CONTRACT")
    if not authorize_claim(
        owner_grant, trusted_hmac_key=trusted_hmac_key,
        expected_plan_sha=prepared.plan_sha256,
        expected_source_sha=prepared.source_sha, required_scope="LOCAL_PLAN",
        now_seconds=now_seconds, trusted_live_consent_check=live_consent_check,
    ):
        raise WorkerHold("NO_OWNER_GO")
    # V1.3 owner-approved Zero-VM policy: absolutely no model-generated
    # script, test or tool may be executed here. The previous injectable
    # sandbox.invoke() path is not a trusted OS enforcement boundary.
    # Approval to draft text is NOT approval to launch untrusted code.
    raise WorkerHold("NO_ISOLATION")
