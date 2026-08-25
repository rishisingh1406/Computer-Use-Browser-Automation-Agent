from typing import Literal

from pydantic import BaseModel, Field


ActionType = Literal[
    "navigate",
    "click",
    "type",
    "scroll",
    "done",
]


class BrowserAction(BaseModel):
    action: ActionType
    url: str | None = None
    selector: str | None = None
    text: str | None = None
    direction: Literal["up", "down"] | None = None
    reason: str = Field(
        description="Why this action is the next step"
    )


class BrowserObservation(BaseModel):
    url: str
    title: str
    text: str
    screenshot_path: str | None = None


class AgentState(BaseModel):
    task: str
    observation: BrowserObservation | None = None
    last_action: BrowserAction | None = None
    step: int = 0
    finished: bool = False
