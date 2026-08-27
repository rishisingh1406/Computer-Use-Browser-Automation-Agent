from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ==========================================================
# LOW-LEVEL BROWSER ACTION
# ==========================================================


class BrowserAction(BaseModel):
    action: Literal[
        "navigate",
        "click",
        "type",
        "scroll",
        "done",
    ]

    url: str | None = None
    selector: str | None = None
    text: str | None = None
    direction: str | None = None
    reason: str


# ==========================================================
# BROWSER OBSERVATION
# ==========================================================


class BrowserObservation(BaseModel):
    url: str
    title: str
    text: str
    screenshot_path: str


# ==========================================================
# VISUAL GROUNDING TARGET
# ==========================================================


class VisionTarget(BaseModel):
    found: bool

    x: int | None = None
    y: int | None = None

    reason: str


# ==========================================================
# BROWSER AGENT STATE
# ==========================================================


class AgentState(BaseModel):
    task: str

    step: int = 0

    observation: BrowserObservation | None = None

    last_action: BrowserAction | None = None

    finished: bool = False

    error: str | None = None

    last_result: dict | None = None


# ==========================================================
# HIGH-LEVEL PLAN
# ==========================================================


class PlanStep(BaseModel):
    step_id: int

    action: Literal[
        "navigate",
        "search",
        "extract",
    ]

    description: str

    target: str | None = None

    expected_result: str | None = None


class BrowserPlan(BaseModel):
    goal: str

    site: str

    steps: list[PlanStep] = Field(
        default_factory=list
    )

    @field_validator("steps")
    @classmethod
    def validate_steps(
        cls,
        steps: list[PlanStep],
    ) -> list[PlanStep]:
        if not steps:
            raise ValueError(
                "BrowserPlan must contain at least one step"
            )

        return steps


# ==========================================================
# PLAN STEP RESULT
# ==========================================================


class PlanStepResult(BaseModel):
    step_id: int

    action: Literal[
        "navigate",
        "search",
        "extract",
    ]

    description: str

    finished: bool

    final_url: str | None = None

    final_title: str | None = None

    extracted_text: str | None = None

    error: str | None = None


# ==========================================================
# COMPLETE PLAN RESULT
# ==========================================================


class PlanRunResult(BaseModel):
    goal: str

    site: str

    completed: bool

    steps: list[PlanStepResult] = Field(
        default_factory=list
    )

    final_result: str | None = None