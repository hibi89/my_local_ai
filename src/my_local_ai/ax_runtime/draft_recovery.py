"""Bounded, optional advice on workbench draft failures."""
from __future__ import annotations

from http.client import HTTPSConnection, HTTPException
import json
import os
import re
from time import monotonic


MAX_DRAFT_ATTEMPTS = 3
GEMINI_MODEL = "gemini-3.5-flash-lite"
# Sending a code requires allowing it here. No user-supplied text leaves the PC.
RECOVERY_ACTIONS = {
    "TIMEOUT": ("compact", "retry"),
    "RESOURCE_LIMIT": ("compact", "retry"),
    "OUTPUT_TOO_LARGE": ("compact", "retry"),
    "OLLAMA_RESPONSE_INVALID": ("compact", "retry"),
    "DRAFT_FORMAT": ("compact", "retry"),
    "DRAFT_SYNTAX": ("compact", "retry"),
    "OLLAMA_UNAVAILABLE": ("retry",),
    "MODEL_BUSY": ("retry",),
}


class GeminiDraftAdvisor:
    def __init__(self) -> None:
        key = os.environ.get("MLA_GEMINI_API_KEY", "").strip()
        self._key = key if re.fullmatch(r"[A-Za-z0-9_-]{20,160}", key) else ""
        self._next_call = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def advise(self, code: str, failed_attempt: int) -> str | None:
        choices = RECOVERY_ACTIONS.get(code)
        if (not self._key or not choices or not 1 <= failed_attempt < MAX_DRAFT_ATTEMPTS
            or monotonic() < self._next_call):
            return None
        payload = json.dumps({
            "contents": [{"parts": [{"text": (
                "Choose a recovery action for a local source-draft model. "
                "retry repeats the bounded attempt. compact shortens supporting document excerpts "
                "and reiterates the output format while keeping the requested change and source scope. "
                f"Failure code: {code}. Failed attempt: {failed_attempt}."
            )}]}],
            "generationConfig": {
                "maxOutputTokens": 256,
                "responseMimeType": "application/json",
                "responseJsonSchema": {
                    "type": "object", "required": ["action"],
                    "properties": {"action": {"type": "string", "enum": list(choices)}},
                },
            },
        }).encode("utf-8")
        conn = HTTPSConnection("generativelanguage.googleapis.com", timeout=10)
        try:
            conn.request("POST", f"/v1beta/models/{GEMINI_MODEL}:generateContent", body=payload,
                         headers={"Content-Type": "application/json", "x-goog-api-key": self._key})
            response = conn.getresponse()
            if response.status != 200:
                # Don't spend more calls on a rejected key or a project at its limit.
                self._next_call = monotonic() + (300 if response.status in (401, 403, 429) else 20)
                return None
            limit = 16_384
            data = response.read(limit + 1)
            if len(data) > limit:
                return None
            candidate = json.loads(data)["candidates"][0]
            if candidate["finishReason"] != "STOP":
                return None
            answer = json.loads(candidate["content"]["parts"][-1]["text"])
            if type(answer) is dict and set(answer) == {"action"} and answer["action"] in choices:
                return answer["action"]
        except (OSError, HTTPException, KeyError, IndexError, TypeError, ValueError, RecursionError):
            self._next_call = monotonic() + 20
        finally:
            conn.close()
        return None
