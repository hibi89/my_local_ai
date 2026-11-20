"""Typed no-egress resource routing for MLA's GTX 1050 Ti Qwen drafts.

This module only chooses a bounded local Ollama profile. It cannot execute
source/test code, start a model, select external APIs, or grant Owner/F18 GO.
"""
from __future__ import annotations

from dataclasses import dataclass

from .provider_policy import ProviderHold

_SHORT = 4096
_MAX = 8192
_MAX_KEEP_ALIVE = 90


@dataclass(frozen=True)
class LocalDraftRoute:
    role: str  # Always LOCAL_QWEN_DRAFT (external provider OFF)
    context_tokens: int
    keep_alive_seconds: int
    source: str = "LOCAL_LOOPBACK_ONLY"


def choose_draft_route(prompt: str, output_tokens: int, *,
                       next_eligible: bool, pause_requested: bool) -> LocalDraftRoute:
    """Choose safe local context and warm residency for one bounded SWU.

    Input bytes are conservatively budgeted against the context including the
    structured output reservation. A final/paused job must not retain the model
    on a low-VRAM GPU after the worker returns.
    """
    if (type(prompt) is not str or not prompt or "\x00" in prompt
        or type(output_tokens) is not int or not 64 <= output_tokens <= 1536
        or type(next_eligible) is not bool or type(pause_requested) is not bool):
        raise ProviderHold("UNSAFE_INPUT")
    try:
        length = len(prompt.encode("utf-8"))
    except UnicodeError:
        raise ProviderHold("UNSAFE_INPUT") from None
    if length > _MAX - output_tokens:
        raise ProviderHold("RESOURCE_LIMIT", detail="PROMPT_TOO_LARGE")
    selected = _SHORT if length <= _SHORT - output_tokens else _MAX
    warm = _MAX_KEEP_ALIVE if next_eligible and not pause_requested else 0
    return LocalDraftRoute("LOCAL_QWEN_DRAFT", selected, warm)
