import pytest

from app.agent.llm import GroqBrowserLLM
from app.agent.models import BrowserObservation


@pytest.mark.asyncio
async def test_groq_decides_next_action():

    llm = GroqBrowserLLM()

    observation = BrowserObservation(
        url="https://example.com/",
        title="Example Domain",
        text="""
        Example Domain

        This domain is for use in documentation examples
        without needing permission.

        Learn more
        """,
        screenshot_path="screenshots/example.png",
    )

    action = await llm.decide(
        task="Open example.com and determine whether the page is ready.",
        observation=observation,
    )

    print("\nMODEL ACTION:")
    print(action.model_dump())

    assert action.action in {
        "navigate",
        "click",
        "type",
        "scroll",
        "done",
    }