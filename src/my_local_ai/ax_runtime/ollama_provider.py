"""Local-only Ollama Qwen provider; no pull, external URL or self-verification.

All model text is UNTRUSTED. Callers must independently enforce PlanSpec,
owner consent, allowed paths, model lease and F18 review. This module neither
executes generated text nor awards VERIFIED receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
from typing import Callable

from .budgets import BudgetExceeded, BudgetGuard
from .provider_policy import LoopbackEndpoint, ProviderHold, require_qwen_model
from .worker_lock import ModelLockBusy, ModelLockUnsafe, OneModelLock

_TAGS_LIMIT = 131_072
_MAX_PROMPT_BYTES = 65_536
STRUCTURED_OUTPUT_TOKENS = 1536


@dataclass(frozen=True)
class ProviderStatus:
    state: str  # AVAILABLE or HOLD; never VERIFIED
    reason: str
    model: str


@dataclass(frozen=True)
class UntrustedGeneration:
    text: str
    model: str
    untrusted: bool = True
    metrics: dict | None = None


def _safe_local_metrics(result: dict) -> dict | None:
    """Only numeric Ollama counters/timings, never model output or source text.

    Invalid or missing telemetry does not turn a successful draft into a failure
    or claim a performance improvement. Ollama durations are in nanoseconds.
    """
    fields = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
              "prompt_eval_count", "eval_count")
    if any(type(result.get(k)) is not int or result[k] < 0
           or result[k] > (900_000_000_000 if k.endswith("duration") else 100_000)
           for k in fields):
        return None
    total_ms, load_ms, prompt_ms, eval_ms = (
        result[k] // 1_000_000 for k in fields[:4]
    )
    count = result["eval_count"]
    speed = round(count * 1_000_000_000 / result["eval_duration"], 1) if result["eval_duration"] else 0.0
    return {"total_ms": total_ms, "load_ms": load_ms,
            "prompt_ms": prompt_ms, "eval_ms": eval_ms,
            "prompt_tokens": result["prompt_eval_count"], "eval_tokens": count,
            "tokens_per_second": speed}


class OllamaProvider:
    def __init__(
        self, *, endpoint: str = "http://127.0.0.1:11434",
        model: str = "qwen3:4b-instruct", timeout_seconds: int = 5,
        connection_factory: Callable[..., object] | None = None,
    ) -> None:
        self.endpoint = LoopbackEndpoint.parse(endpoint)
        self.model = require_qwen_model(model)
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 270:
            raise ProviderHold("RESOURCE_LIMIT")
        self.timeout_seconds = timeout_seconds
        self._connection_factory = connection_factory or http.client.HTTPConnection

    def _request(self, method: str, path: str, *, payload: dict | None = None,
                 limit: int = _TAGS_LIMIT) -> dict:
        # Literal IP only: no DNS, proxy, userinfo, redirects, or environment
        # credentials. No general-purpose URL/path forwarding.
        if (method, path) not in {("GET", "/api/tags"), ("POST", "/api/generate")}:
            raise ProviderHold("UNSAFE_ENDPOINT")
        body = None if payload is None else json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        connection = None
        try:
            connection = self._connection_factory(
                self.endpoint.host, self.endpoint.port, timeout=self.timeout_seconds,
            )
            headers = {"Accept": "application/json", "Host": (
                f"[{self.endpoint.host}]:{self.endpoint.port}"
                if ":" in self.endpoint.host else f"{self.endpoint.host}:{self.endpoint.port}"
            )}
            if body is not None:
                headers["Content-Type"] = "application/json"
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                raise ProviderHold("OLLAMA_UNAVAILABLE")
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ProviderHold("RESOURCE_LIMIT", detail="OUTPUT_TOO_LARGE" if payload else "")
            if not isinstance(data, bytes):
                raise ProviderHold("OLLAMA_RESPONSE_INVALID")
            def reject_duplicate_keys(pairs):
                obj = {}
                for key, value in pairs:
                    if key in obj:
                        raise ValueError("duplicate Ollama JSON key")
                    obj[key] = value
                return obj
            parsed = json.loads(
                data, object_pairs_hook=reject_duplicate_keys,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
            if not isinstance(parsed, dict):
                raise ProviderHold("OLLAMA_RESPONSE_INVALID")
            return parsed
        except ProviderHold:
            raise
        except TimeoutError:
            raise ProviderHold("OLLAMA_UNAVAILABLE", detail="TIMEOUT") from None
        except (OSError, http.client.HTTPException):
            raise ProviderHold("OLLAMA_UNAVAILABLE") from None
        except (UnicodeError, json.JSONDecodeError, ValueError, TypeError, OverflowError):
            raise ProviderHold("OLLAMA_RESPONSE_INVALID") from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def available(self) -> ProviderStatus:
        try:
            result = self._request("GET", "/api/tags")
            items = result.get("models")
            if not isinstance(items, list) or len(items) > 1024:
                raise ProviderHold("OLLAMA_RESPONSE_INVALID")
            names = {
                item.get("name") for item in items
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            if self.model not in names:
                raise ProviderHold("MODEL_ABSENT")
            return ProviderStatus("AVAILABLE", "LOCAL_MODEL_PRESENT", self.model)
        except ProviderHold as error:
            return ProviderStatus("HOLD", error.code, self.model)

    def generate(self, prompt: str, *, model_lock: OneModelLock,
                 budget: BudgetGuard, allow_generation: bool = False,
                 structured: bool = False,
                 structured_tokens: int = STRUCTURED_OUTPUT_TOKENS,
                 keep_alive_seconds: int = 0) -> UntrustedGeneration:
        # No owner consent is minted here: caller must provide a trusted
        # authorization and explicitly opt in. Always HOLD by default.
        if allow_generation is not True:
            raise ProviderHold("GENERATION_DISABLED")
        if not isinstance(model_lock, OneModelLock):
            raise ProviderHold("NO_MODEL_LOCK")
        if not isinstance(budget, BudgetGuard):
            raise ProviderHold("NO_BUDGET")
        if (type(structured) is not bool or type(structured_tokens) is not int
            or not 64 <= structured_tokens <= STRUCTURED_OUTPUT_TOKENS
            or type(keep_alive_seconds) is not int or not 0 <= keep_alive_seconds <= 90):
            raise ProviderHold("UNSAFE_INPUT")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderHold("UNSAFE_INPUT")
        try:
            prompt_bytes = prompt.encode("utf-8")
            if len(prompt_bytes) > _MAX_PROMPT_BYTES or "\x00" in prompt:
                raise ProviderHold("UNSAFE_INPUT")
            # The resource guard conservatively counts prompt bytes as tokens.
            if len(prompt_bytes) > budget.limits.max_context_tokens:
                raise ProviderHold("RESOURCE_LIMIT", detail="PROMPT_TOO_LARGE")
            budget.check(context_tokens=len(prompt_bytes), output_bytes=0)
        except (UnicodeError, BudgetExceeded):
            raise ProviderHold("RESOURCE_LIMIT") from None

        # An absent model never triggers /api/pull or implicit network download.
        status = self.available()
        if status.state != "AVAILABLE":
            raise ProviderHold(status.reason)
        try:
            with model_lock:
                budget.reserve_call()
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": f"{keep_alive_seconds}s" if keep_alive_seconds else 0,
                    "options": {"num_ctx": budget.limits.max_context_tokens},
                }
                if structured:
                    payload["format"] = "json"
                    payload["options"].update(temperature=0, num_predict=structured_tokens)
                result = self._request("POST", "/api/generate", payload=payload,
                    limit=min(1_048_576, budget.limits.max_output_bytes + 16384))
                answer = result.get("response")
                if result.get("done") is not True or not isinstance(answer, str):
                    raise ProviderHold("OLLAMA_RESPONSE_INVALID")
                try:
                    encoded = answer.encode("utf-8")
                except UnicodeError:
                    raise ProviderHold("OLLAMA_RESPONSE_INVALID") from None
                if len(encoded) > budget.limits.max_output_bytes:
                    raise ProviderHold("RESOURCE_LIMIT", detail="OUTPUT_TOO_LARGE")
                budget.check(output_bytes=len(encoded))
                return UntrustedGeneration(answer, self.model, metrics=_safe_local_metrics(result))
        except ModelLockBusy:
            raise ProviderHold("RESOURCE_LIMIT", detail="MODEL_BUSY") from None
        except (ModelLockUnsafe, OSError):
            raise ProviderHold("RESOURCE_LIMIT", detail="MODEL_LOCK") from None
        except BudgetExceeded:
            raise ProviderHold("RESOURCE_LIMIT") from None
