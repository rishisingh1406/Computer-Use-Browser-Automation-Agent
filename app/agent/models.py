from typing import Literal

from pydantic import BaseModel, Field


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


class BrowserObservation(BaseModel):
    url: str
    title: str
    text: str
    screenshot_path: str


class VisionTarget(BaseModel):
    found: bool
    x: int | None = None
    y: int | None = None
    reason: str


from typing import Literal

from pydantic import BaseModel


class VisionTarget(BaseModel):
    found: bool
    x: int | None = None
    y: int | None = None
    reason: str