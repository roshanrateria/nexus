"""Real-key smoke test for the four agent roles.

Prints the resolved mode, then, per role:
  chat        plain text round trip (fails loudly when finish_reason == "length")
  image       image_url input with a tiny base64 PNG -- executor/verifier only;
              planner/reporter stay text-only, so they are never probed with pixels
  tools       bind_tools(add) must produce a tool call
  structured  with_structured_output(..., strict=False) must return a valid object
  effort      (once per Meta model) a cheap call must accept reasoning_effort="low"

Usage:  python scripts/smoke_endpoints.py
Exits non-zero when anything fails. Needs MODEL_API_KEY in .env
(and BASETEN_API_KEY for hybrid mode). All other settings are code defaults.
"""

import argparse
import json
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path = list(dict.fromkeys(sys.path))

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.table import Table

from agent import BASETEN_BASE_URL, BASETEN_MODEL, META_BASE_URL, check_model_key, resolve_mode, role_endpoint
from schemas import PlannerDecision, Settings

ROLES = ("planner", "executor", "verifier", "reporter")

# Caps keep base64 screenshots from flooding the console.
REQUEST_BODY_LIMIT = 4000
RESPONSE_BODY_LIMIT = 2000
_BASE64_URL_RE = re.compile(r'"url"\s*:\s*"data:[^"]{64,}"')


class HttpDebug:
    """--debug: an httpx event hook that prints method, URL, redacted request
    JSON and (on status >= 400 or finish_reason == "length") the response body.

    Redaction first: the string equal to any API key is replaced wherever it
    would appear; base64 image payloads are collapsed to a length marker.
    """

    def __init__(self, keys: list[str]):
        self.keys = [key for key in keys if key]

    def redact(self, text: str) -> str:
        for key in self.keys:
            text = text.replace(key, "***REDACTED***")
        if "data:" in text and "base64" in text:
            text = _BASE64_URL_RE.sub('"url": "data:image/<base64 image elided>"', text)
        return text

    def redact_headers(self, headers) -> str:
        parts = []
        for name, value in headers.items():
            if name.lower() == "authorization":
                value = "***REDACTED***" if value else value
            parts.append(f"{name}: {value}")
        return self.redact("; ".join(parts))

    def client(self) -> httpx.Client:
        def log_request(request: httpx.Request) -> None:
            try:
                body = request.content.decode("utf-8", "replace") if request.content else ""
            except Exception:
                body = ""
            print(f"[http] {request.method} {request.url}", flush=True)
            if body:
                shown = self.redact(body)
                if len(shown) > REQUEST_BODY_LIMIT:
                    shown = shown[:REQUEST_BODY_LIMIT] + f" ...[+{len(shown) - REQUEST_BODY_LIMIT} chars]"
                print(f"[http] request body: {shown}", flush=True)

        def log_response(response: httpx.Response) -> None:
            content_type = response.headers.get("content-type", "")
            # Only JSON bodies are read here; SSE streams (text/event-stream) are
            # consumed by the SDK afterwards, so they must stay untouched.
            if "application/json" not in content_type:
                return
            try:
                body_text = response.read().decode("utf-8", "replace")
            except Exception:
                return
            if response.status_code >= 400:
                shown = self.redact(body_text)
                if len(shown) > RESPONSE_BODY_LIMIT:
                    shown = shown[:RESPONSE_BODY_LIMIT] + f" ...[+{len(shown) - RESPONSE_BODY_LIMIT} chars]"
                print(f"[http] response {response.status_code} ({content_type}): {shown}", flush=True)
                return
            try:
                finish = (json.loads(body_text).get("choices") or [{}])[0].get("finish_reason")
            except Exception:
                return
            if finish == "length":
                print(f'[http] response 200 finish_reason="length": {self.redact(body_text)[:RESPONSE_BODY_LIMIT]}', flush=True)

        return httpx.Client(event_hooks={"request": [log_request], "response": [log_response]})

PNG_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

IMAGE_MESSAGE = [
    HumanMessage(
        content=[
            {"type": "text", "text": "Look at the attached image. Reply with the single word VISIBLE."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG_1PX}"}},
        ]
    )
]


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def finish_reason(message) -> str:
    return (message.response_metadata or {}).get("finish_reason") or ""


def assert_not_truncated(message, label: str) -> None:
    """Reasoning tokens count toward max_tokens: a "length" finish means the answer
    (or JSON) was cut off, which would silently break structured outputs."""
    reason = finish_reason(message)
    if reason == "length":
        raise AssertionError(f'{label} hit max_tokens (finish_reason="length"): raise the role MAX_TOKENS')
    if reason not in ("stop", "tool_calls", ""):
        raise AssertionError(f"{label} finished abnormally (finish_reason={reason!r})")


def chat_check(llm: ChatOpenAI) -> str:
    message = llm.invoke("Reply with the single word OK.")
    assert message.text.strip(), "empty response"
    assert_not_truncated(message, "chat")
    return "ok"


def image_check(llm: ChatOpenAI) -> str:
    message = llm.invoke(IMAGE_MESSAGE)
    assert message.text.strip(), "empty response"
    assert_not_truncated(message, "image input")
    return "ok"


def tools_check(llm: ChatOpenAI) -> str:
    result = llm.bind_tools([add]).invoke("Use the add tool to compute 2+3. Do not answer in plain text.")
    assert_not_truncated(result, "tools")
    assert result.tool_calls, f"no tool call, replied {result.text[:60]!r}"
    return f"add({result.tool_calls[0]['args']})"


def structured_check(llm: ChatOpenAI, settings: Settings) -> str:
    result = llm.with_structured_output(PlannerDecision, method=settings.structured_method, strict=False).invoke(
        "Goal: open https://example.com in the browser and confirm the page loads. Produce the initial plan."
    )
    assert isinstance(result, PlannerDecision), "not a PlannerDecision"
    return f"status={result.status}, steps={len(result.plan)}"


def reasoning_effort_check(model: str, api_key: str, debug: HttpDebug | None = None) -> str:
    extra: dict = {}
    if debug is not None:
        extra["http_client"] = debug.client()
    low = ChatOpenAI(
        model=model,
        base_url=META_BASE_URL,
        api_key=api_key,
        max_tokens=512,
        reasoning_effort="low",
        max_retries=1,
        stream_usage=True,
        **extra,
    )
    message = low.invoke("Reply with the single word OK.")
    assert message.text.strip(), "empty response"
    assert_not_truncated(message, "reasoning_effort=low")
    return "accepted"


def make_llm(role: str, settings: Settings, debug: HttpDebug | None = None) -> tuple[ChatOpenAI, str]:
    """The exact per-role ChatOpenAI that agent.build_models would create."""
    endpoint = role_endpoint(settings, role)
    meta = endpoint == "cloud"
    extra: dict = {}
    if debug is not None:
        extra["http_client"] = debug.client()
    return (
        ChatOpenAI(
            model=getattr(settings, f"{role}_model") if meta else BASETEN_MODEL,
            base_url=META_BASE_URL if meta else BASETEN_BASE_URL,
            api_key=settings.model_api_key if meta else settings.baseten_api_key,
            max_tokens=getattr(settings, f"{role}_max_tokens"),
            reasoning_effort=getattr(settings, f"{role}_reasoning_effort") if meta else None,
            max_retries=1,
            stream_usage=True,
            **extra,
        ),
        endpoint,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-key smoke test for the four agent roles")
    parser.add_argument("--debug", action="store_true", help="httpx event hook: log method, URL, redacted request JSON, error/length response bodies")
    args = parser.parse_args()
    console = Console()
    load_dotenv()
    try:
        settings = Settings.from_env()
    except Exception as error:
        console.print(f"[red]Environment not configured: {error}")
        console.print("[red]Put MODEL_API_KEY=... (and optionally BASETEN_API_KEY) in .env.")
        sys.exit(1)
    debug = HttpDebug([settings.model_api_key, settings.baseten_api_key]) if args.debug else None

    mode = resolve_mode(settings)
    console.print(
        f"[cyan]Mode: {'HYBRID | planner+reporter -> Meta Spark | executor+verifier -> Baseten' if mode == 'hybrid' else 'CLOUD-ONLY | all roles -> Meta Spark'}[/]"
    )
    check_model_key(settings)

    table = Table(title="Endpoint smoke test")
    for column in ("role/endpoint/model", "check", "result", "detail"):
        table.add_column(column, overflow="fold")

    failed = 0
    seen_low: set[str] = set()
    for role in ROLES:
        llm, endpoint = make_llm(role, settings, debug)
        meta = endpoint == "cloud"
        model = getattr(settings, f"{role}_model") if meta else BASETEN_MODEL
        label = f"{role} ({endpoint}) {model}"

        checks: list[tuple[str, object | None]] = [
            ("chat", lambda llm=llm: chat_check(llm)),
            # planner and reporter stay text-only: no pixels are ever probed
            ("image", None if role in ("planner", "reporter") else lambda llm=llm: image_check(llm)),
            ("tools", lambda llm=llm: tools_check(llm)),
            ("structured (strict=False)", lambda llm=llm, s=settings: structured_check(llm, s)),
        ]
        if meta and model not in seen_low:
            checks.append(("reasoning_effort='low'", lambda m=model, k=settings.model_api_key, d=debug: reasoning_effort_check(m, k, d)))
            seen_low.add(model)

        for name, check_fn in checks:
            if check_fn is None:
                table.add_row(label, name, "SKIP", "text-only role: planner/reporter must not send pixels")
                label = ""
                continue
            try:
                result, detail = "PASS", check_fn()
            except Exception as error:
                failed += 1
                result = "FAIL"
                detail = f"{type(error).__name__}: {error}"[:220].strip()
                traceback.print_exc(file=sys.stderr)
            table.add_row(label, name, result, detail)
            label = ""

    console.print(table)
    if not failed:
        console.print("[green]All endpoint checks passed.[/]")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
