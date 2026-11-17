"""My Local AI V1.3: zero-VM, zero-container, nonexecuting Pure Player.

The only model transport is literal 127.0.0.1 Ollama /api/generate for
PUBLIC_SYNTHETIC prompts. Model output is nontrusted data; no shell, process
from generated content, dynamic Python import, test runner, VM, AppContainer,
WSL2, Docker, Windows Sandbox or Windows-container fallback is supported.

Pure operators perform CPU-only source/path/syntax checks. They do NOT
attest OS-wide network isolation, protected owner identity, independent F18,
or grant writes, Git promotion, runtime execution or Production deployment.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
import json
import re

from my_local_ai.ax_runtime.budgets import BudgetExceeded, BudgetGuard
from my_local_ai.ax_runtime.provider_policy import (
    LoopbackEndpoint, ProviderHold, require_qwen_model,
)
from my_local_ai.contracts.task import safe_path
from my_local_ai.security.codeshield_contracts import (
    CodeShieldContext, CodeShieldHold, DataClass, checked_relative_path,
)

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}\Z")
_MAX_FILES = 16
_MAX_FILE_BYTES = 65536
_MAX_TOTAL_BYTES = 131072
_OPERATORS = frozenset({"PLAN_SCOPE_REVIEW", "STATIC_AST_REVIEW"})


class WindowsIsolationHold(ValueError):
    """Legacy-compatible *denial* only; this is not an isolation executor."""
    def __init__(self, reason: str = "UNTRUSTED_EXECUTION_DISABLED"):
        allowed = {
            "UNTRUSTED_EXECUTION_DISABLED", "INVALID_SANDBOX_SCOPE",
            "UNSAFE_GUEST_CONFIG", "NETWORK_EGRESS_UNVERIFIED",
            "OWNER_SIGNER_NOT_AVAILABLE", "STATIC_SOURCE_HOLD",
        }
        self.code = reason if reason in allowed else "UNTRUSTED_EXECUTION_DISABLED"
        super().__init__(self.code)


def _strict_json(raw: bytes, *, limit: int) -> object:
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")

    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
            out[key] = value
        return out

    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique,
            parse_constant=lambda _v: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None


def _validated_files(
    allowed_paths: tuple[str, ...], proposed: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    if (type(allowed_paths) is not tuple or not 1 <= len(allowed_paths) <= _MAX_FILES
        or len(set(allowed_paths)) != len(allowed_paths)
        or any(type(p) is not str or p != checked_relative_path(p)
               for p in allowed_paths)
        or type(proposed) is not dict
        or not 1 <= len(proposed) <= len(allowed_paths)):
        raise CodeShieldHold("UNSAFE_PATH")
    total, checked, seen = 0, [], set()
    for name, content in proposed.items():
        if (type(name) is not str or type(content) is not str
            or "\x00" in content or name.casefold() in seen
            or name not in allowed_paths
            or name != checked_relative_path(name)):
            raise CodeShieldHold("UNSAFE_PATH")
        seen.add(name.casefold())
        try:
            size = len(content.encode("utf-8"))
        except UnicodeError:
            raise CodeShieldHold("UNTRUSTED_DECISION") from None
        total += size
        if size > _MAX_FILE_BYTES or total > _MAX_TOTAL_BYTES:
            raise CodeShieldHold("UNSAFE_PATH")
        checked.append((name, content))
    return tuple(sorted(checked))


@dataclass(frozen=True)
class HostQwenGenerationRequest:
    task_id: str
    run_id: str
    source_sha: str
    plan_sha256: str
    allowed_paths: tuple[str, ...]
    prompt_sha256: str
    request_sha256: str
    request_body: bytes
    model: str = "qwen3:4b-instruct"
    endpoint: str = "http://127.0.0.1:11434"
    state: str = "HOST_QWEN_PUBLIC_SYNTHETIC_DATA_ONLY"
    host_inference_executed: bool = False
    generated_code_executed: bool = False
    owner_go_verified: bool = False
    independent_f18_verified: bool = False
    can_promote: bool = False

    def __post_init__(self):
        if (not _ID.fullmatch(self.task_id)
            or not _ID.fullmatch(self.run_id)
            or not _SHA40.fullmatch(self.source_sha)
            or not _SHA64.fullmatch(self.plan_sha256)
            or not _SHA64.fullmatch(self.prompt_sha256)
            or not _SHA64.fullmatch(self.request_sha256)
            or self.model != "qwen3:4b-instruct"
            or self.endpoint != "http://127.0.0.1:11434"
            or self.state != "HOST_QWEN_PUBLIC_SYNTHETIC_DATA_ONLY"
            or any(getattr(self, name) is not False for name in (
                "host_inference_executed", "generated_code_executed",
                "owner_go_verified", "independent_f18_verified", "can_promote",
            ))):
            raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")


@dataclass(frozen=True)
class UntrustedHostQwenFiles:
    task_id: str
    run_id: str
    source_sha: str
    plan_sha256: str
    request_sha256: str
    files: tuple[tuple[str, str], ...]
    files_sha256: str
    state: str = "UNTRUSTED_HOST_MODEL_OUTPUT_F18_REQUIRED"
    files_applied_to_original: bool = False
    generated_code_executed: bool = False
    independent_f18_verified: bool = False
    can_publish: bool = False


def prepare_host_qwen_generation(
    context: CodeShieldContext, *, run_id: str, coding_request: str,
    classification: str = "PUBLIC_SYNTHETIC_ONLY",
    model: str = "qwen3:4b-instruct",
    endpoint_url: str = "http://127.0.0.1:11434",
) -> HostQwenGenerationRequest:
    """Controller-scoped Qwen request on host, entirely independent of VM."""
    if (not isinstance(context, CodeShieldContext)
        or context.data_class != DataClass.PUBLIC_SYNTHETIC
        or type(run_id) is not str or not _ID.fullmatch(run_id)
        or run_id != context.run_id
        or classification != "PUBLIC_SYNTHETIC_ONLY"
        or type(coding_request) is not str
        or not coding_request.strip() or "\x00" in coding_request
        or len(coding_request.encode("utf-8")) > 8192):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    try:
        endpoint = LoopbackEndpoint.parse(endpoint_url)
        selected = require_qwen_model(model)
    except ProviderHold:
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED") from None
    if (selected != "qwen3:4b-instruct"
        or endpoint.host != "127.0.0.1"
        or endpoint_url != "http://127.0.0.1:11434"):
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED")
    paths = context.allowed_paths
    _validated_files(paths, {paths[0]: ""})
    schema = ('Return only JSON {"version":1,"files":['
              '{"path":"allowed/relative.py","content":"complete UTF-8 source"}'
              ']}. Use only these exact allowed paths: ')
    prompt = schema + ", ".join(paths) + ". No tools, shell, network or install. Task: " + coding_request
    body = json.dumps({
        "model":selected, "prompt":prompt, "stream":False,
        "format":"json", "options":{
            "temperature":0,"num_predict":2048,"num_ctx":4096,
        }, "keep_alive":"0",
    }, ensure_ascii=True, sort_keys=True, separators=(",",":")).encode("utf-8")
    if len(body) > 14000:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    identity = (
        b"mla-pure-host-qwen/v1|" + context.fingerprint_sha256.encode("ascii")
        + b"|" + run_id.encode("ascii") + b"|" + body
    )
    return HostQwenGenerationRequest(
        context.task_id, run_id, context.source_git_sha, context.plan_sha256,
        paths, sha256(prompt.encode("utf-8")).hexdigest(),
        sha256(identity).hexdigest(), body,
    )


def _check_generation_request(
    request: HostQwenGenerationRequest, context: CodeShieldContext,
) -> None:
    if (not isinstance(request, HostQwenGenerationRequest)
        or not isinstance(context, CodeShieldContext)
        or context.data_class != DataClass.PUBLIC_SYNTHETIC
        or (request.task_id,request.run_id,request.source_sha,request.plan_sha256)
          != (context.task_id,context.run_id,context.source_git_sha,context.plan_sha256)
        or request.allowed_paths != context.allowed_paths
        or request.model != "qwen3:4b-instruct"
        or request.endpoint != "http://127.0.0.1:11434"
        or request.host_inference_executed or request.generated_code_executed
        or request.owner_go_verified or request.independent_f18_verified
        or request.can_promote):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    body = _strict_json(request.request_body, limit=14000)
    if (not isinstance(body,dict)
        or set(body) != {"model","prompt","stream","format","options","keep_alive"}
        or body["model"] != request.model
        or not isinstance(body["prompt"],str)
        or not body["prompt"].startswith('Return only JSON {"version":1,"files":[')
        or sha256(body["prompt"].encode("utf-8")).hexdigest() != request.prompt_sha256
        or body["stream"] is not False or body["format"] != "json"
        or body["keep_alive"] != "0"
        or body["options"] != {"temperature":0,"num_predict":2048,"num_ctx":4096}):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    identity = (
        b"mla-pure-host-qwen/v1|" + context.fingerprint_sha256.encode("ascii")
        + b"|" + request.run_id.encode("ascii") + b"|" + request.request_body
    )
    if sha256(identity).hexdigest() != request.request_sha256:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")


def decode_untrusted_host_qwen_files(
    raw_ollama_response: bytes, request: HostQwenGenerationRequest,
    context: CodeShieldContext,
) -> UntrustedHostQwenFiles:
    """Parse bounded model-authored source text, never execute or write."""
    _check_generation_request(request, context)
    response = _strict_json(raw_ollama_response, limit=262144)
    if (not isinstance(response,dict)
        or response.get("model") != request.model
        or response.get("done") is not True
        or not isinstance(response.get("response"),str)
        or len(response["response"].encode("utf-8")) > _MAX_TOTAL_BYTES
        or "tool_calls" in response or "message" in response):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    parsed = _strict_json(response["response"].encode("utf-8"), limit=_MAX_TOTAL_BYTES)
    if (not isinstance(parsed,dict) or set(parsed) != {"version","files"}
        or type(parsed["version"]) is not int or parsed["version"] != 1
        or not isinstance(parsed["files"],list)
        or not 1 <= len(parsed["files"]) <= len(request.allowed_paths)):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    d = {}
    for entry in parsed["files"]:
        if (type(entry) is not dict or set(entry) != {"path","content"}
            or type(entry["path"]) is not str
            or entry["path"] in d):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        d[entry["path"]] = entry["content"]
    try:
        files = _validated_files(request.allowed_paths, d)
    except (CodeShieldHold, ValueError):
        raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG") from None
    content = json.dumps(files,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")
    return UntrustedHostQwenFiles(
        request.task_id,request.run_id,request.source_sha,request.plan_sha256,
        request.request_sha256,files,
        sha256(b"mla-untrusted-host-files/v1|" + content).hexdigest(),
    )


def infer_host_qwen_public_synthetic(
    request: HostQwenGenerationRequest, context: CodeShieldContext,
    *, budget: BudgetGuard,
) -> UntrustedHostQwenFiles:
    """Real local loopback inference, no dynamic tool and no virtual guest."""
    _check_generation_request(request, context)
    if not isinstance(budget, BudgetGuard):
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")
    try:
        budget.reserve_call()
    except BudgetExceeded:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE") from None
    connection = None
    try:
        connection = HTTPConnection("127.0.0.1",11434,timeout=20)
        connection.request(
            "POST","/api/generate",body=request.request_body,
            headers={"Content-Type":"application/json",
                     "Accept":"application/json","Connection":"close"},
        )
        response = connection.getresponse()
        if (response.status != 200
            or not response.getheader("Content-Type","").lower().startswith("application/json")):
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
        raw = response.read(262145)
        if len(raw)>262144:
            raise WindowsIsolationHold("UNSAFE_GUEST_CONFIG")
    except (OSError,TimeoutError,ValueError,HTTPException):
        raise WindowsIsolationHold("NETWORK_EGRESS_UNVERIFIED") from None
    finally:
        if connection is not None:
            connection.close()
    try:
        budget.check(output_bytes=len(raw))
    except BudgetExceeded:
        raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE") from None
    return decode_untrusted_host_qwen_files(raw,request,context)


@dataclass(frozen=True)
class PurePlayerCandidate:
    context_sha256: str
    candidate_git_sha: str
    source_git_sha: str
    plan_sha256: str
    operator_id: str
    files: tuple[tuple[str,str],...]
    payload_sha256: str
    stage: str = "UNTRUSTED_NONEXECUTING_CANDIDATE"
    source_execution_allowed: bool = False
    generated_tests_execution_allowed: bool = False
    owner_approval_verified: bool = False
    independent_f18_verified: bool = False
    git_promotion_allowed: bool = False
    network_egress_attested: bool = False

    def __post_init__(self):
        if (self.stage != "UNTRUSTED_NONEXECUTING_CANDIDATE"
            or type(self.operator_id) is not str or self.operator_id not in _OPERATORS
            or any(getattr(self,n) is not False for n in (
                "source_execution_allowed","generated_tests_execution_allowed",
                "owner_approval_verified","independent_f18_verified",
                "git_promotion_allowed","network_egress_attested",
            ))):
            raise WindowsIsolationHold("INVALID_SANDBOX_SCOPE")


def prepare_pure_player_candidate(
    context: CodeShieldContext, *,
    operator_id: str, proposed_files: dict[str,str] | None = None,
) -> PurePlayerCandidate:
    """Non-executing, fixed typed operator request with exact scoped files."""
    if (not isinstance(context,CodeShieldContext)
        or type(operator_id) is not str or operator_id not in _OPERATORS):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    if operator_id == "PLAN_SCOPE_REVIEW":
        if proposed_files is not None:
            raise CodeShieldHold("UNTRUSTED_DECISION")
        files=()
    else:
        if type(proposed_files) is not dict:
            raise CodeShieldHold("UNSAFE_PATH")
        files=_validated_files(context.allowed_paths,proposed_files)
    canonical=json.dumps({
        "context":context.fingerprint_sha256,
        "candidate":context.candidate_git_sha,
        "plan":context.plan_sha256,"source":context.source_git_sha,
        "operation":operator_id,"files":files,
    },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")
    return PurePlayerCandidate(
        context.fingerprint_sha256, context.candidate_git_sha,
        context.source_git_sha, context.plan_sha256,
        operator_id, files, sha256(canonical).hexdigest(),
    )


def run_pure_player_nonexecuting_candidate(
    context: CodeShieldContext, candidate: PurePlayerCandidate,
) -> dict[str,object]:
    """CPU syntax inspection only, no generated tests, shell or network."""
    if (not isinstance(candidate,PurePlayerCandidate)
        or not isinstance(context,CodeShieldContext)
        or any(getattr(candidate,key) is not False for key in (
            "source_execution_allowed","generated_tests_execution_allowed",
            "owner_approval_verified","independent_f18_verified",
            "git_promotion_allowed","network_egress_attested",
        ))):
        raise CodeShieldHold("UNTRUSTED_DECISION")
    verified=prepare_pure_player_candidate(
        context,operator_id=candidate.operator_id,
        proposed_files=(dict(candidate.files)
                        if candidate.operator_id=="STATIC_AST_REVIEW" else None),
    )
    if candidate!=verified:
        raise CodeShieldHold("STALE_EVIDENCE")
    syntax="NOT_APPLICABLE"
    nodes=0
    if candidate.operator_id=="STATIC_AST_REVIEW":
        syntax="SYNTAX_SHAPE_ONLY"
        for name,source in candidate.files:
            if not name.casefold().endswith(".py"):
                syntax="NON_PYTHON_NEEDS_SEPARATE_STATIC_SCAN_HOLD"
                break
            try:
                parsed=ast.parse(source,filename="<untrusted_candidate>")
            except (SyntaxError,ValueError,MemoryError,RecursionError):
                syntax="PYTHON_SYNTAX_HOLD"
                break
            for _ in ast.walk(parsed):
                nodes+=1
                if nodes>12000:
                    syntax="AST_RESOURCE_HOLD"
                    break
            if syntax=="AST_RESOURCE_HOLD":
                break
    return {
        "stage":"PURE_PLAYER_NONEXECUTING_HOLD",
        "operator_id":candidate.operator_id,
        "payload_sha256":candidate.payload_sha256,
        "file_count":len(candidate.files),"syntax":syntax,
        "context_sha256":candidate.context_sha256,
        "candidate_git_sha":candidate.candidate_git_sha,
        "fixed_operator_invoked":True,
        "model_output_trusted":False,
        "generated_code_executed":False,
        "generated_tests_executed":False,
        "network_egress_allowed":False,
        "host_network_isolation_attested":False,
        "owner_go_verified":False,"independent_f18_verified":False,
        "git_promotion_allowed":False,"p2":"LOCKED",
    }


def deny_pure_player_network_operation(operation_id: str) -> None:
    """Deny unlisted operators, including dynamic network/shell invocation."""
    if type(operation_id) is not str or operation_id not in _OPERATORS:
        raise CodeShieldHold("UNTRUSTED_EXECUTION_DENIED")
    return None


def _capabilities_read_only_main() -> int:
    """No VM capability request or feature detection; no privileged I/O."""
    print(json.dumps({
        "runtime":"CPU_PURE_PLAYER_NO_VM_NO_CONTAINER",
        "vm_required":False,"container_required":False,
        "generated_code_execution_allowed":False,
        "host_network_isolation_attested":False,
        "owner_go":False,"independent_f18_verified":False,
        "p2":"LOCKED",
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(_capabilities_read_only_main())
