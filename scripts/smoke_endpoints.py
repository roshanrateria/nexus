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

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path = list(dict.fromkeys(sys.path))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.table import Table

from agent import BASETEN_BASE_URL, BASETEN_MODEL, META_BASE_URL, check_model_key, resolve_mode, role_endpoint
from schemas import PlannerDecision, Settings

ROLES = ("planner", "executor", "verifier", "reporter")

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


def reasoning_effort_check(model: str, api_key: str) -> str:
    low = ChatOpenAI(
        model=model,
        base_url=META_BASE_URL,
        api_key=api_key,
        max_tokens=512,
        reasoning_effort="low",
        max_retries=1,
        stream_usage=True,
    )
    message = low.invoke("Reply with the single word OK.")
    assert message.text.strip(), "empty response"
    assert_not_truncated(message, "reasoning_effort=low")
    return "accepted"


def make_llm(role: str, settings: Settings) -> tuple[ChatOpenAI, str]:
    """The exact per-role ChatOpenAI that agent.build_models would create."""
    endpoint = role_endpoint(settings, role)
    meta = endpoint == "cloud"
    return (
        ChatOpenAI(
            model=getattr(settings, f"{role}_model") if meta else BASETEN_MODEL,
            base_url=META_BASE_URL if meta else BASETEN_BASE_URL,
            api_key=settings.model_api_key if meta else settings.baseten_api_key,
            max_tokens=getattr(settings, f"{role}_max_tokens"),
            reasoning_effort=getattr(settings, f"{role}_reasoning_effort") if meta else None,
            max_retries=1,
            stream_usage=True,
        ),
        endpoint,
    )


def main() -> None:
    console = Console()
    load_dotenv()
    try:
        settings = Settings.from_env()
    except Exception as error:
        console.print(f"[red]Environment not configured: {error}")
        console.print("[red]Put MODEL_API_KEY=... (and optionally BASETEN_API_KEY) in .env.")
        sys.exit(1)

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
        llm, endpoint = make_llm(role, settings)
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
            checks.append(("reasoning_effort='low'", lambda m=model, k=settings.model_api_key: reasoning_effort_check(m, k)))
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
