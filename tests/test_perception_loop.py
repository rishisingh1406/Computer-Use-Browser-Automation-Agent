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

    async def decide(
        self,
        task,
        observation,
        failure_feedback=None,
    ):
        """
        Fake LLM used for testing the perception-action loop.

        Day 100 compatibility:
            failure_feedback is accepted so the fake model
            matches the production BrowserAgent LLM interface.

        This test does not need to use failure_feedback because
        it tests the normal successful perception-action path.
        """

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

    try:
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

        # The fake LLM should have been called twice:
        # 1. Navigate to example.com
        # 2. Mark the task as done
        assert llm.calls == 2

    finally:
        await manager.close()
