"""The single gateway to the LLM API.

Every model call in the project goes through an ``LLM`` so that we can swap models in one
place, keep token accounting for cost estimates, and run the whole stack offline with
``ScriptedLLM`` in tests. Do not construct ``anthropic.Anthropic`` anywhere else.

Two real backends: ``ClaudeLLM`` (Anthropic API key) and ``ClaudeCodeLLM`` (the local
Claude Code CLI, which runs on whatever plan Claude Code is logged into; for one person's
local use, not for serving other people).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from negotrain import config
from negotrain.budget import SpendLedger

T = TypeVar("T", bound=BaseModel)
Message = dict[str, Any]  # {"role": "user" | "assistant", "content": str}


class CachedText(str):
    """Ordinary text with explicit prefix boundaries for the API backend only.

    Parts concatenate verbatim; local CLI and scripted clients still see a string.
    Unmarked parts remain separate blocks so growing histories can find earlier writes.
    """

    def __new__(cls, *parts: str, cache_indices: tuple[int, ...] | None = None):
        if not parts or any(not isinstance(p, str) or not p for p in parts):
            raise ValueError("cache parts must be nonempty strings")
        indices = tuple(range(len(parts))) if cache_indices is None else cache_indices
        if len(set(indices)) != len(indices) or any(i < 0 or i >= len(parts) for i in indices):
            raise ValueError("invalid cache indices")
        value = super().__new__(cls, "".join(parts))
        value.parts = tuple(parts)
        value.cache_indices = tuple(indices)
        return value

    def blocks(self, ttl: str = "5m") -> list[dict]:
        return [
            {"type": "text", "text": part}
            | (
                {"cache_control": {"type": "ephemeral", "ttl": ttl}}
                if i in self.cache_indices
                else {}
            )
            for i, part in enumerate(self.parts)
        ]

    def append_uncached(self, text: str) -> CachedText:
        return CachedText(*self.parts, text, cache_indices=self.cache_indices)


def cached_json(
    *sections: dict, prefix: str = "", cache_indices: tuple[int, ...] | None = None
) -> CachedText:
    """Serialize disjoint object sections with independently reusable prefixes."""
    keys = [key for section in sections for key in section]
    if not sections or any(not section for section in sections) or len(keys) != len(set(keys)):
        raise ValueError("JSON cache sections must be nonempty with distinct keys")
    parts = [json.dumps(section)[1:-1] for section in sections]
    parts[0] = prefix + "{" + parts[0]
    for i in range(1, len(parts)):
        parts[i] = ", " + parts[i]
    parts[-1] += "}"
    return CachedText(*parts, cache_indices=cache_indices)


class LLMRefusal(RuntimeError):
    pass


class LLMTruncated(RuntimeError):
    pass


class LLM(Protocol):
    def complete(
        self, system: str, messages: Sequence[Message], *, max_tokens: int = 16000
    ) -> str: ...

    def parse(
        self,
        system: str,
        messages: Sequence[Message],
        output_type: type[T],
        *,
        max_tokens: int = 16000,
    ) -> T: ...


# USD per million tokens for cost estimates (claude-opus-5-5; update if the model changes).
PRICE_PER_MTOK = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}
MODEL_PRICES = {
    "claude-opus-5-5": PRICE_PER_MTOK,
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.10, "cache_write": 2.5},
}


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_creation_5m_input_tokens: int = 0
    cache_creation_1h_input_tokens: int = 0
    cache_hit_calls: int = 0
    fallback_cache_ttl: str = "5m"
    prices: dict = field(default_factory=lambda: dict(PRICE_PER_MTOK))
    # Rollouts call the API from several threads.
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, usage: Any) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += usage.input_tokens or 0
            self.output_tokens += usage.output_tokens or 0
            self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
            created = getattr(usage, "cache_creation_input_tokens", 0) or 0
            self.cache_creation_input_tokens += created
            detail = getattr(usage, "cache_creation", None)

            def count(name):
                return (
                    detail.get(name, 0) if isinstance(detail, dict) else getattr(detail, name, 0)
                ) or 0

            hour = count("ephemeral_1h_input_tokens")
            short = count("ephemeral_5m_input_tokens")
            # Older clients may omit the TTL breakdown. If 1h writes were requested,
            # conservatively price any unspecified writes at 1h rather than underbill.
            unspecified = max(0, created - hour - short)
            if self.fallback_cache_ttl == "1h":
                hour += unspecified
            else:
                short += unspecified
            self.cache_creation_1h_input_tokens += hour
            self.cache_creation_5m_input_tokens += short
            self.cache_hit_calls += bool(getattr(usage, "cache_read_input_tokens", 0))

    def cost(self) -> float:
        """Estimated USD, using provider-reported cache write TTLs when available."""
        p = self.prices
        return (
            self.input_tokens * p["input"]
            + self.output_tokens * p["output"]
            + self.cache_read_input_tokens * p["cache_read"]
            + (self.cache_creation_input_tokens - self.cache_creation_1h_input_tokens)
            * p["cache_write"]
            + self.cache_creation_1h_input_tokens * (2 * p["input"])
        ) / 1e6

    def snapshot(self) -> dict:
        with self._lock:
            total_input = (
                self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens
            )
            return {
                name: getattr(self, name)
                for name in (
                    "calls",
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                    "cache_creation_5m_input_tokens",
                    "cache_creation_1h_input_tokens",
                    "cache_hit_calls",
                )
            } | {
                "estimated_usd": self.cost(),
                "total_input_tokens": total_input,
                "cache_read_fraction": self.cache_read_input_tokens / total_input
                if total_input
                else 0.0,
                "cache_hit_call_fraction": self.cache_hit_calls / self.calls if self.calls else 0.0,
                "estimated_uncached_usd": (
                    total_input * self.prices["input"] + self.output_tokens * self.prices["output"]
                )
                / 1e6,
            }


class ClaudeLLM:
    """Claude via the Anthropic SDK. Credentials come from ANTHROPIC_API_KEY (see .env)."""

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        client: anthropic.Anthropic | None = None,
        ledger: SpendLedger | None = None,
        cache_ttl: str | None = None,
    ):
        self.model = model or config.model()
        self.effort = effort or config.effort()
        self.cache_ttl = cache_ttl if cache_ttl is not None else config.cache_ttl()
        if self.cache_ttl not in ("5m", "1h"):
            raise ValueError("cache_ttl must be 5m or 1h")
        if self.model not in MODEL_PRICES:
            raise ValueError("model needs verified pricing and a context bound before API use")
        self.client = (client or anthropic.Anthropic()).with_options(max_retries=0, timeout=180)
        self.ledger = ledger or SpendLedger(config.REPO_ROOT / ".api-budget.sqlite3")
        self.usage = Usage(prices=MODEL_PRICES[self.model], fallback_cache_ttl=self.cache_ttl)

    def _request(self, system: str, messages: Sequence[Message], max_tokens: int) -> dict:
        system_blocks = (system if isinstance(system, CachedText) else CachedText(system)).blocks(
            self.cache_ttl
        )
        rendered = []
        explicit_messages = False
        for message in messages:
            content = message["content"]
            if isinstance(content, CachedText):
                explicit_messages = True
                # The changing conversation gets cheap, short-lived entries. Longer
                # system TTLs always precede shorter message TTLs as required by the API.
                content = content.blocks("5m")
            else:
                content = deepcopy(content)
            if isinstance(content, list):
                explicit_messages |= any("cache_control" in b for b in content)
            rendered.append({**message, "content": content})
        blocks = system_blocks + [
            b for m in rendered if isinstance(m["content"], list) for b in m["content"]
        ]
        breakpoints = sum("cache_control" in b for b in blocks)
        if breakpoints > 4:
            raise ValueError("at most four cache breakpoints are supported")
        request = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": rendered,
            "output_config": {"effort": self.effort},
        }
        # Explicit message boundaries stop before changing controller/deadline suffixes.
        # Automatic caching there would pay to write a prefix we will never reuse.
        if not explicit_messages and breakpoints < 4 and rendered:
            request["cache_control"] = {"type": "ephemeral", "ttl": "5m"}
        return request

    def _check(self, response: Any, reservation: str) -> None:
        request_usage = Usage(prices=MODEL_PRICES[self.model], fallback_cache_ttl=self.cache_ttl)
        request_usage.add(response.usage)
        self.ledger.settle(reservation, request_usage.cost(), request_usage.snapshot())
        self.usage.add(response.usage)
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise LLMRefusal(f"model declined (category={category})")
        if response.stop_reason == "max_tokens":
            raise LLMTruncated("response hit max_tokens; raise the limit for this call")

    def complete(self, system: str, messages: Sequence[Message], *, max_tokens: int = 16000) -> str:
        response = self._call(system, messages, max_tokens)
        return "".join(b.text for b in response.content if b.type == "text")

    def _call(
        self,
        system: str,
        messages: Sequence[Message],
        max_tokens: int,
        output_type: type[T] | None = None,
    ):
        if not 1 <= max_tokens <= 64000:
            raise ValueError("invalid output token bound")
        # Reserve the ENTIRE documented 1M context at the most expensive input/cache
        # rate (1h writes), plus max output. This avoids treating token-count estimates
        # as hard bounds. Normal usage releases the unused reserve immediately.
        request = self._request(system, messages, max_tokens)
        prices = MODEL_PRICES[self.model]
        bound = 2 * prices["input"] + max_tokens * prices["output"] / 1e6
        reservation = self.ledger.reserve(self.model, bound, wait_seconds=180)
        raw = None
        try:
            if output_type is None:
                response = self.client.beta.messages.create(**request)
            else:
                # Account for provider usage BEFORE Pydantic parses generated JSON.
                # Truncated JSON can fail validation even though the request was billed.
                raw = self.client.beta.messages.with_raw_response.parse(
                    **request, output_format=output_type
                )
                response = anthropic.types.beta.BetaMessage.model_validate(raw.http_response.json())
        except Exception as error:
            self.ledger.uncertain(reservation, type(error).__name__)
            raise
        self._check(response, reservation)
        return raw.parse() if raw is not None else response

    def parse(
        self,
        system: str,
        messages: Sequence[Message],
        output_type: type[T],
        *,
        max_tokens: int = 16000,
    ) -> T:
        try:
            response = self._call(system, messages, max_tokens, output_type)
        except LLMTruncated:
            if max_tokens >= 64000:
                raise
            # One explicit retry, separately reserved and billed. No hidden SDK retry.
            response = self._call(system, messages, min(64000, 2 * max_tokens), output_type)
        if response.parsed_output is None:
            raise RuntimeError("model returned no parseable output")
        return response.parsed_output


def check_api_key(api_key: str) -> str | None:
    """None if ``api_key`` authenticates, else a short reason. Lists one model, which bills
    no tokens, so the app can validate a pasted key immediately."""
    try:
        anthropic.Anthropic(api_key=api_key, max_retries=0).models.list(limit=1)
    except anthropic.AuthenticationError:
        return "that key was rejected (check for a typo or a revoked key)"
    except anthropic.PermissionDeniedError:
        return "that key doesn't have permission to use the API"
    except anthropic.APIConnectionError:
        return "couldn't reach the Anthropic API (are you offline?)"
    except anthropic.APIStatusError as e:
        return f"the API returned an error ({e.status_code})"
    return None


# Variables Claude Code sets for its own child processes. Stripped so `claude -p` runs as a
# fresh top-level session even when this app was started from inside Claude Code.
_PARENT_SESSION_VARS = ("CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT")


def _child_env() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if k not in _PARENT_SESSION_VARS and not k.startswith("CLAUDE_CODE_")
    }


def flatten(messages: Sequence[Message]) -> str:
    """One prompt from a multi-turn history: `claude -p` takes a single message."""
    if len(messages) == 1:
        return str(messages[0]["content"])
    parts = ["The conversation so far (your own earlier replies are marked YOU):"]
    for m in messages:
        who = "YOU" if m["role"] == "assistant" else "THEM"
        parts.append(f"--- {who} ---\n{m['content']}")
    parts.append("--- END ---\nWrite your reply to the last message.")
    return "\n\n".join(parts)


class ClaudeCodeLLM:
    """Claude through the local Claude Code CLI (`claude -p`), so no API key is needed:
    calls count against the plan Claude Code is logged into.

    Each call is a fresh, tool-less, non-persisted session started from an empty working
    directory (so no project files or CLAUDE.md are pulled in). Structured output uses
    ``--json-schema``. Slower than the API (process start-up, no prompt caching across
    calls) and subject to the plan's rate limits.
    """

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        binary: str | None = None,
        timeout: float = 300,
    ):
        self.model = model or config.model()
        self.effort = effort or config.effort()
        self.binary = binary or config.claude_bin()
        if not self.binary:
            raise RuntimeError("Claude Code CLI not found (install it or set NEGOTRAIN_CLAUDE_BIN)")
        self.timeout = timeout
        self.workdir = tempfile.mkdtemp(prefix="negotrain-claude-")
        self.usage = Usage()

    def _command(self, system: str, schema: dict | None) -> list[str]:
        cmd = [
            self.binary,
            "-p",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--effort",
            self.effort,
            "--tools",
            "",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--system-prompt",
            system,
        ]
        if schema is not None:
            cmd += ["--json-schema", json.dumps(schema)]
        return cmd

    def _run(self, system: str, messages: Sequence[Message], schema: dict | None) -> dict:
        try:
            proc = subprocess.run(
                self._command(system, schema),
                input=flatten(messages),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workdir,
                env=_child_env(),
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Claude Code took longer than {self.timeout:.0f}s") from e
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            detail = (proc.stderr or proc.stdout).strip()[-400:]
            raise RuntimeError(f"Claude Code failed (exit {proc.returncode}): {detail}") from None
        usage = data.get("usage") or {}
        self.usage.add(
            SimpleNamespace(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
                cache_creation=usage.get("cache_creation"),
            )
        )
        if data.get("stop_reason") == "refusal":
            raise LLMRefusal("model declined (via Claude Code)")
        if data.get("is_error") or proc.returncode != 0:
            raise RuntimeError(f"Claude Code error: {str(data.get('result', ''))[:400]}")
        return data

    def complete(self, system: str, messages: Sequence[Message], *, max_tokens: int = 16000) -> str:
        return str(self._run(system, messages, None).get("result", ""))

    def parse(
        self,
        system: str,
        messages: Sequence[Message],
        output_type: type[T],
        *,
        max_tokens: int = 16000,
    ) -> T:
        data = self._run(system, messages, output_type.model_json_schema())
        out = data.get("structured_output")
        if out is None:
            try:
                out = json.loads(data.get("result") or "")
            except json.JSONDecodeError:
                raise RuntimeError("Claude Code returned no structured output") from None
        return output_type.model_validate(out)


Responder = Callable[[str, Sequence[Message]], Any]


@dataclass
class ScriptedLLM:
    """Offline stand-in for tests and UI work. Returns scripted responses in order.

    Each script entry is a string (for ``complete``), a pydantic model or dict (for
    ``parse``), or a callable ``(system, messages) -> response`` for dynamic behavior.
    Every call is recorded in ``calls`` so tests can assert on prompts.
    """

    script: list[Any]
    calls: list[tuple[str, list[Message]]] = field(default_factory=list)

    def _next(self, system: str, messages: Sequence[Message]) -> Any:
        self.calls.append((system, list(messages)))
        if not self.script:
            raise RuntimeError("ScriptedLLM ran out of scripted responses")
        item = self.script.pop(0)
        return item(system, messages) if callable(item) else item

    def complete(self, system: str, messages: Sequence[Message], *, max_tokens: int = 16000) -> str:
        return str(self._next(system, messages))

    def parse(
        self,
        system: str,
        messages: Sequence[Message],
        output_type: type[T],
        *,
        max_tokens: int = 16000,
    ) -> T:
        item = self._next(system, messages)
        return item if isinstance(item, output_type) else output_type.model_validate(item)
