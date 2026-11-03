"""Provider smoke test for the four agent roles.

For each role's endpoint+model it runs four probes:
  chat        plain text round trip
  image       image_url input with a tiny base64 PNG constant
  tools       bind_tools(add) must produce a tool call
  structured  with_structured_output(PlannerDecision) must return a valid object

Usage:  python scripts/smoke_endpoints.py
Exits non-zero when anything fails. Credentials come from .env (see .env.example).
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

from agent import META_BASE_URL
from schemas import PlannerDecision, Settings

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


def chat_check(llm: ChatOpenAI) -> str:
    message = llm.invoke("Reply with the single word OK.")
    assert message.text.strip(), "empty response"
    return "ok"


def image_check(llm: ChatOpenAI) -> str:
    message = llm.invoke(IMAGE_MESSAGE)
    assert message.text.strip(), "empty response"
    return "ok"


def tools_check(llm: ChatOpenAI) -> str:
    result = llm.bind_tools([add]).invoke("Use the add tool to compute 2+3. Do not answer in plain text.")
    assert result.tool_calls, f"no tool call, replied {result.text[:60]!r}"
    return f"add({result.tool_calls[0]['args']})"


def structured_check(llm: ChatOpenAI) -> str:
    result = llm.with_structured_output(PlannerDecision).invoke(
        "Goal: open https://example.com in the browser and confirm the page loads. Produce the initial plan."
    )
    assert isinstance(result, PlannerDecision), "not a PlannerDecision"
    return f"status={result.status}, steps={len(result.plan)}"


def make_llm(role: str, settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=getattr(settings, f"{role}_model"),
        base_url=META_BASE_URL,
        api_key=settings.model_api_key,
        max_tokens=getattr(settings, f"{role}_max_tokens"),
        max_retries=1,
        stream_usage=True,
    )


ROLES = ("planner", "executor", "verifier", "reporter")
CHECKS = (("chat", chat_check), ("image", image_check), ("tools", tools_check), ("structured", structured_check))


def main() -> None:
    console = Console()
    load_dotenv()
    try:
        settings = Settings.from_env()
    except Exception as error:
        console.print(f"[red]Environment not configured: {error}")
        console.print("[red]Copy .env.example to .env and fill in real endpoint values and keys.")
        sys.exit(1)

    table = Table(title="Endpoint smoke test")
    for column in ("role/endpoint/model", "check", "result", "detail"):
        table.add_column(column, overflow="fold")
    failed = 0
    for role in ROLES:
        model = getattr(settings, f"{role}_model")
        label = f"{role} (meta) {model}"
        llm = make_llm(role, settings)
        for name, check in CHECKS:
            try:
                result, detail = "PASS", check(llm)
            except Exception as error:
                failed += 1
                result = "FAIL"
                detail = f"{type(error).__name__}: {error}"[:220].strip()
                traceback.print_exc(file=sys.stderr)
            table.add_row(label, name, result, detail)
            label = ""
    console.print(table)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
