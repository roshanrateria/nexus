"""Privacy Ledger: measures what leaves the machine, to which endpoint.

Counters are thread-safe and kept per endpoint ("cloud", "open") and per role
(planner/executor/verifier/reporter). The planner and reporter handlers are
always text-only: they raise PrivacyViolation if any image part shows up.
"""

import threading
import time
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage

# Meta Model API Standard-mode pricing for muse-spark-1.3, USD per 1M tokens
# (input 1.25, cached input 0.15, output 4.25). The open-weights endpoint is
# free of billed tokens (it runs on Baseten credits), so only "cloud" gets a cost.
PRICE_PER_1M: dict[str, dict[str, float]] = {
    "muse-spark-1.3": {"input": 1.25, "cached_input": 0.15, "output": 4.25},
}
DEFAULT_PRICE = PRICE_PER_1M["muse-spark-1.3"]


class PrivacyViolation(Exception):
    """A text-only endpoint was about to receive image content."""


class Ledger:
    def __init__(self, on_change: Any = None, throttle_seconds: float = 0.2):
        self._lock = threading.Lock()
        self._on_change = on_change
        self._throttle_seconds = throttle_seconds
        self._last_emit = 0.0
        self._by_endpoint: dict[str, dict[str, int]] = {}
        self._by_role: dict[str, dict[str, int]] = {}
        self._planner_calls = 0
        self._cost_usd = 0.0

    @staticmethod
    def _blank() -> dict[str, int]:
        return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "bytes_out": 0, "images_out": 0}

    @staticmethod
    def _bump(table: dict[str, dict[str, int]], key: str, fields: dict[str, int]) -> None:
        row = table.setdefault(key, Ledger._blank())
        for name, delta in fields.items():
            row[name] += delta

    def record_start(self, role: str, endpoint: str, bytes_out: int, images_out: int) -> None:
        with self._lock:
            self._bump(self._by_endpoint, endpoint, {"calls": 1, "bytes_out": bytes_out, "images_out": images_out})
            self._bump(self._by_role, role, {"calls": 1, "bytes_out": bytes_out, "images_out": images_out})
            if role == "planner":
                self._planner_calls += 1
        self._emit()

    def record_usage(self, role: str, endpoint: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0, model: str = "") -> None:
        with self._lock:
            fields = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cached_tokens": cached_tokens}
            self._bump(self._by_endpoint, endpoint, fields)
            self._bump(self._by_role, role, fields)
            if endpoint == "cloud":
                price = PRICE_PER_1M.get(model, DEFAULT_PRICE)
                self._cost_usd += (
                    (prompt_tokens - cached_tokens) * price["input"]
                    + cached_tokens * price["cached_input"]
                    + completion_tokens * price["output"]
                ) / 1_000_000
        self._emit()

    def reset(self) -> None:
        """Zero every counter for the next run and emit a fresh snapshot."""
        with self._lock:
            self._by_endpoint.clear()
            self._by_role.clear()
            self._planner_calls = 0
            self._cost_usd = 0.0
            self._last_emit = 0.0
        self._emit()

    def snapshot(self) -> dict:
        with self._lock:
            cloud = {**self._blank(), **dict(self._by_endpoint.get("cloud", {}))}
            open_side = {**self._blank(), **dict(self._by_endpoint.get("open", {}))}
            open_tokens = open_side["prompt_tokens"] + open_side["completion_tokens"]
            cloud_tokens = cloud["prompt_tokens"] + cloud["completion_tokens"]
            total = open_tokens + cloud_tokens
            return {
                "cloud": cloud,
                "open": open_side,
                "by_role": {role: dict(row) for role, row in self._by_role.items()},
                "planner_calls": self._planner_calls,
                "open_token_share": round(open_tokens / total, 4) if total else 0.0,
                # Billed Meta endpoint spend; the open endpoint runs on Baseten credits.
                "cost_usd": round(self._cost_usd, 6),
            }

    def _emit(self) -> None:
        """Call on_change with the snapshot, throttled to at most 5 per second."""
        now = time.monotonic()
        if now - self._last_emit < self._throttle_seconds or self._on_change is None:
            self._last_emit = now
            return
        self._last_emit = now
        try:
            self._on_change(self.snapshot())
        except Exception:
            pass  # a dashboard hiccup must never break an agent run


class LedgerHandler(AsyncCallbackHandler):
    raise_error = True

    def __init__(self, ledger: Ledger, role: str, endpoint: str, text_only: bool, model: str = ""):
        self.ledger = ledger
        self.role = role
        self.endpoint = endpoint
        self.text_only = text_only
        self.model = model
        self._prompt_chars = 0

    @staticmethod
    def _scan(message: Any) -> tuple[int, int]:
        chars = 0
        images = 0
        content = message.content if isinstance(message, BaseMessage) else message
        if isinstance(content, str):
            chars = len(content.encode("utf-8"))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    images += 1
                    chars += len(str(part).encode("utf-8"))
                elif isinstance(part, dict):
                    chars += len(str(part).encode("utf-8"))
                elif isinstance(part, str):
                    chars += len(part.encode("utf-8"))
                else:
                    chars += len(str(part).encode("utf-8"))
        else:
            chars = len(str(content).encode("utf-8"))
        return chars, images

    async def on_chat_model_start(self, serialized: dict, messages: list[list[BaseMessage]], **kwargs) -> None:
        chars = 0
        images = 0
        for batch in messages:
            for message in batch:
                part_chars, part_images = self._scan(message)
                chars += part_chars
                images += part_images
        self._prompt_chars = chars
        if self.text_only and images:
            raise PrivacyViolation(
                f"{self.role} endpoint '{self.endpoint}' is text-only; refused to send {images} image(s)"
            )
        self.ledger.record_start(self.role, self.endpoint, chars, images)

    async def on_llm_end(self, response: Any, **kwargs) -> None:
        usage = (response.llm_output or {}).get("token_usage") or {}
        if not usage and response.generations and response.generations[0]:
            message = getattr(response.generations[0][0], "message", None)
            usage = getattr(message, "usage_metadata", None) or {}
        prompt_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        # Cached tokens: prompt_tokens_details.cached_tokens (OpenAI shape) or
        # input_token_details.cache_read (langchain usage_metadata shape).
        details = usage.get("prompt_tokens_details")
        if isinstance(details, dict):
            cached_tokens = int(details.get("cached_tokens") or 0)
        else:
            cached_tokens = int(getattr(details, "cached_tokens", 0) or 0)
        if not cached_tokens:
            details = usage.get("input_token_details") or {}
            cached_tokens = int(details.get("cache_read") or 0) if isinstance(details, dict) else 0
        if not (prompt_tokens or completion_tokens):
            generation_text = sum(len(generation.text or "") for batch in response.generations for generation in batch)
            prompt_tokens, completion_tokens = self._prompt_chars // 4, generation_text // 4
        self.ledger.record_usage(self.role, self.endpoint, prompt_tokens, completion_tokens, cached_tokens=cached_tokens, model=self.model)
