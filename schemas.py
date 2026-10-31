import operator
import os
from typing import Annotated, Literal, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, Json, model_validator


class Settings(BaseModel):
    cloud_base_url: str
    cloud_api_key: str
    open_base_url: str
    open_api_key: str
    structured_method: Literal["json_schema", "function_calling", "json_mode"]
    planner_endpoint: Literal["cloud", "open"]
    planner_model: str
    executor_endpoint: Literal["cloud", "open"]
    executor_model: str
    verifier_endpoint: Literal["cloud", "open"]
    verifier_model: str
    reporter_endpoint: Literal["cloud", "open"]
    reporter_model: str
    rate_limit_rpm: float
    llm_max_attempts: int
    retry_initial_seconds: float
    retry_max_seconds: float
    max_planner_rounds: int
    max_step_iterations: int
    # Retry the same step this many times with a different approach before involving the planner.
    max_local_retries: int = 2
    recursion_limit: int
    max_observation_chars: int
    max_page_text_chars: int
    max_artifact_chars: int
    max_links: int
    verifier_page_text_chars: int
    event_text_chars: int
    observation_viewport_margin: int
    screenshot_quality: int
    action_timeout_ms: int
    navigation_timeout_ms: int
    settle_ms: int
    typing_delay_ms: int
    browser_headless: bool
    browser_channel: str
    browser_profile_dir: str
    browser_viewport_width: int
    browser_viewport_height: int
    browser_locale: str
    browser_timezone: str
    browser_extra_headers: Json[dict[str, str]]
    browser_launch_args: Json[list[str]]
    checkpoint_db: str
    reports_dir: str
    dashboard_host: str
    dashboard_port: int
    dashboard_open: bool
    dashboard_max_log: int
    allow_run_javascript: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        values: dict[str, object] = {}
        missing = []
        for name in cls.model_fields:
            raw = os.environ.get(name.upper())
            if raw is None:
                field = cls.model_fields[name]
                if field.is_required():
                    missing.append(name.upper())
                else:
                    values[name] = field.get_default()
            else:
                values[name] = raw
        if missing:
            raise KeyError(f"missing required environment variables: {', '.join(missing)}")
        return cls(**values)


class PlanStep(BaseModel):
    instruction: str = Field(description="Self-contained instruction for the browser operator, including exactly what information to record when information is needed")
    expected_outcome: str = Field(description="Observable condition that proves the step is done")


class PlannerDecision(BaseModel):
    thought: str = Field(description="Brief reasoning about what happened and why the plan stays or changes")
    status: Literal["continue", "goal_achieved", "goal_unreachable"]
    plan: list[PlanStep] = Field(default_factory=list, description="Full list of remaining steps, the first is executed next; empty unless status is continue")
    final_assessment: str = Field(default="", description="Required unless status is continue: what was found and where each requirement of the goal is covered, or what was tried and what blocks progress")

    @model_validator(mode="after")
    def check_consistency(self) -> "PlannerDecision":
        if self.status == "continue" and not self.plan:
            raise ValueError("status continue requires a non-empty plan")
        if self.status != "continue" and not self.final_assessment.strip():
            raise ValueError("a terminal status requires a final_assessment")
        return self


class Evidence(BaseModel):
    url: str = Field(description="Exact URL of the page where the text appeared")
    original_text: str = Field(description="Verbatim contiguous excerpt copied from the provided material")
    summarized: str = Field(description="One or two sentences on what the excerpt establishes, with exact figures")


class VerificationResult(BaseModel):
    assessment: str = Field(description="What proves the step complete, or precisely what is missing or wrong and what to do differently")
    complete: bool
    verdict: Literal["done", "retry", "replan"] = Field(description="done = the step is proven complete; retry = the same step can succeed with a different approach; replan = the step is impossible as written or the plan itself is wrong")
    evidences: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_verdict(self) -> "VerificationResult":
        if self.complete != (self.verdict == "done"):
            raise ValueError('complete must be true exactly when verdict is "done"')
        return self


class EmptyArgs(BaseModel):
    pass


class NavigateArgs(BaseModel):
    url: str = Field(description="Absolute URL or path relative to the current page")


class ClickArgs(BaseModel):
    index: int = Field(description="Element index from the current page state")


class TypeTextArgs(BaseModel):
    index: int = Field(description="Element index from the current page state")
    text: str = Field(description="Text to type")
    submit: bool = Field(default=False, description="Press Enter after typing")
    clear: bool = Field(default=True, description="Clear the existing value first")


class PressKeyArgs(BaseModel):
    key: str = Field(description="Key or combination such as Enter, Escape, PageDown, Control+A")


class SelectOptionArgs(BaseModel):
    index: int = Field(description="Index of the native select element")
    option: str = Field(description="Visible label or value of the option")


class HoverArgs(BaseModel):
    index: int = Field(description="Element index from the current page state")


class ScrollArgs(BaseModel):
    direction: Literal["up", "down"]
    pages: float = Field(default=1.0, gt=0, le=10, description="Number of viewport heights to scroll")
    index: Optional[int] = Field(default=None, description="Index of a scrollable element; omit to scroll the page")


class ScrollToTextArgs(BaseModel):
    text: str = Field(description="Visible text to bring into view")


class GetPageTextArgs(BaseModel):
    index: Optional[int] = Field(default=None, description="Element index to read; omit to read the whole page")
    start: int = Field(default=0, ge=0, description="Character offset to continue from when a previous output was cut off")
    include_links: bool = Field(default=False, description="Also list links with absolute URLs")


class RunJavascriptArgs(BaseModel):
    expression: str = Field(description="JavaScript expression or arrow function whose result is JSON serialisable")


class WaitArgs(BaseModel):
    seconds: float = Field(default=2.0, gt=0, le=30, description="Seconds to pause")


class TabArgs(BaseModel):
    tab_index: int = Field(description="Tab index from the Tabs list")


class NewTabArgs(BaseModel):
    url: str = Field(description="Absolute URL to open")


class AgentState(TypedDict, total=False):
    goal: str
    run_id: str
    plan: list[dict]
    history: Annotated[list[dict], operator.add]
    current_step: str
    executor_report: str
    step_artifacts: str
    browser_url: str
    planner_rounds: int
    local_retries: int
    evidence_counter: int
    status: str
    final_assessment: str
    report_path: str


class ExecutorInput(TypedDict):
    current_step: str
    run_id: str


class ExecutorOutput(TypedDict):
    executor_report: str
    step_artifacts: str


class ExecutorState(TypedDict, total=False):
    current_step: str
    run_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    iterations: int
    observation: str
    screenshot: str
    executor_report: str
    step_artifacts: str