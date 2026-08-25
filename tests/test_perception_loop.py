import pytest

from app.agent.executor import ActionExecutor
from app.agent.loop import BrowserAgent
from app.agent.models import BrowserAction
from app.agent.perception import Perception
from app.browser.manager import BrowserManager
from app.browser.tools import BrowserTools


class FakeLLM:

    def __init__(self):
        self.calls = 0

    async def decide(self, task, observation):

        self.calls += 1

        if self.calls == 1:
            return BrowserAction(
                action="navigate",
                url="https://example.com",
                reason="Open the target website",
            )

        return BrowserAction(
            action="done",
            reason="The page was successfully observed",
        )


@pytest.mark.asyncio
async def test_perception_action_loop():

    manager = BrowserManager(headless=True)

    page = await manager.start()

    tools = BrowserTools(page)

    perception = Perception(tools)

    executor = ActionExecutor(tools)

    llm = FakeLLM()

    agent = BrowserAgent(
        llm=llm,
        perception=perception,
        executor=executor,
        max_steps=5,
    )

    state = await agent.run(
        "Open example.com"
    )

    assert state.finished is True
    assert state.step == 2
    assert state.observation is not None
    assert state.observation.title == "Example Domain"

    await manager.close()
