"""Fail-closed policy for local Qwen/Ollama connections.

This guards only this Python connector; system-wide egress isolation is a
separate OS/F18 gate and is NOT established by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import urlsplit

_MODEL = re.compile(r"qwen(?:3|3-coder|2\.5-coder):[A-Za-z0-9_.+-]{1,64}\Z", re.ASCII)


class ProviderHold(RuntimeError):
    """Safe, redacted reason to hold an unavailable/unsafe local provider."""

    def __init__(self, code: str, *, detail: str = ""):
        if code not in {
            "UNSAFE_ENDPOINT", "UNAPPROVED_MODEL", "GENERATION_DISABLED",
            "NO_MODEL_LOCK", "NO_BUDGET", "MODEL_ABSENT", "OLLAMA_UNAVAILABLE",
            "OLLAMA_RESPONSE_INVALID", "RESOURCE_LIMIT", "UNSAFE_INPUT",
        }:
            code = "OLLAMA_UNAVAILABLE"
        self.code = code
        self.detail = detail if detail in {
            "PROMPT_TOO_LARGE", "MODEL_BUSY", "MODEL_LOCK", "OUTPUT_TOO_LARGE", "TIMEOUT",
        } else ""
        super().__init__(code)


@dataclass(frozen=True)
class LoopbackEndpoint:
    host: str
    port: int

    @classmethod
    def parse(cls, url: str) -> "LoopbackEndpoint":
        if not isinstance(url, str) or not url.isascii() or len(url) > 100 or url.strip() != url:
            raise ProviderHold("UNSAFE_ENDPOINT")
        try:
            parts = urlsplit(url)
            if (parts.scheme != "http" or parts.username is not None
                or parts.password is not None or parts.path not in ("", "/")
                or parts.query or parts.fragment or not parts.hostname):
                raise ValueError("unsafe URL component")
            host = parts.hostname
            address = ipaddress.ip_address(host)
            if (not address.is_loopback or address.is_unspecified
                or (isinstance(address, ipaddress.IPv6Address)
                    and address.ipv4_mapped is not None)):
                raise ValueError("non-loopback address")
            port = parts.port
            if port is None or not (1 <= port <= 65535):
                raise ValueError("explicit port required")
            # Reject URL aliases, zone identifiers and parser normalization tricks.
            expected = f"[{address.compressed}]" if address.version == 6 else address.compressed
            if parts.netloc != f"{expected}:{port}":
                raise ValueError("noncanonical authority")
            return cls(str(address), port)
        except (ValueError, TypeError):
            raise ProviderHold("UNSAFE_ENDPOINT") from None


def require_qwen_model(name: str) -> str:
    if not isinstance(name, str) or not name.isascii() or not _MODEL.fullmatch(name):
        raise ProviderHold("UNAPPROVED_MODEL")
    return name
