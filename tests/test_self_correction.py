import pytest

from app.agent.executor import ActionExecutor
from app.agent.loop import BrowserAgent
from app.agent.models import BrowserAction
from app.agent.perception import Perception
from app.browser.manager import BrowserManager
from app.browser.tools import BrowserTools


class RecoveryLLM:
    """
    Fake LLM used to verify self-correction.

    First decision:
        intentionally produces a bad action.

    Second decision:
        receives failure feedback and chooses a different action.
    """

    def __init__(self):
        self.calls = 0
        self.feedback_history = []

    async def decide(
        self,
        task,
        observation,
        failure_feedback=None,
    ):
        self.calls += 1
        self.feedback_history.append(failure_feedback)

        # First decision: intentionally fail.
        if self.calls == 1:
            return BrowserAction(
                action="click",
                selector="#does-not-exist",
                reason="Intentionally invalid selector for recovery test",
            )

        # Recovery decision must receive failure feedback.
        if failure_feedback:
            assert "previous browser action failed" in (
                failure_feedback.lower()
            )
            assert "#does-not-exist" in failure_feedback

        # Choose a completely different action.
        return BrowserAction(
            action="navigate",
            url="https://example.com",
            reason="Recover by navigating to the target page",
        )


@pytest.mark.asyncio
async def test_agent_self_corrects_after_failed_action():
    """
    Verify:

        bad action
            ↓
        execution failure
            ↓
        failure recorded
            ↓
        fresh observation
            ↓
        failure feedback sent to LLM
            ↓
        alternate action
            ↓
        success
    """

    manager = BrowserManager(headless=True)

    try:
        page = await manager.start()

        tools = BrowserTools(page)
        perception = Perception(tools)
        executor = ActionExecutor(tools)
        llm = RecoveryLLM()

        agent = BrowserAgent(
            llm=llm,
            perception=perception,
            executor=executor,
            max_steps=3,
            max_action_retries=2,
        )

        state = await agent.run("Open example.com")

        # The LLM must have been called at least twice:
        # 1. bad click
        # 2. recovery navigation
        assert llm.calls >= 2

        # At least one call must have received failure feedback.
        assert any(
            feedback is not None
            for feedback in llm.feedback_history
        )

        # The failed action must have been recorded.
        assert len(state.failed_actions) >= 1

        # The invalid selector should appear in the recorded failure.
        assert any(
            "#does-not-exist" in failed
            for failed in state.failed_actions
        )

        # Agent should have a fresh observation.
        assert state.observation is not None

    finally:
        await manager.close()


class AlwaysFailLLM:
    """
    Fake LLM that always produces an invalid action.

    Used to verify that the agent respects the retry budget
    instead of retrying forever.
    """

    def __init__(self):
        self.calls = 0

    async def decide(
        self,
        task,
        observation,
        failure_feedback=None,
    ):
        self.calls += 1

        return BrowserAction(
            action="click",
            selector="#never-exists",
            reason="Intentional permanent failure",
        )


@pytest.mark.asyncio
async def test_agent_respects_retry_limit():
    """
    Verify that repeated failures terminate once the
    configured retry budget is exhausted.
    """

    manager = BrowserManager(headless=True)

    try:
        page = await manager.start()

        tools = BrowserTools(page)
        perception = Perception(tools)
        executor = ActionExecutor(tools)
        llm = AlwaysFailLLM()

        agent = BrowserAgent(
            llm=llm,
            perception=perception,
            executor=executor,
            max_steps=2,
            max_action_retries=2,
        )

        state = await agent.run(
            "Perform an impossible click"
        )

        # Agent must not report successful completion.
        assert state.finished is False

        # There must be an error after retry exhaustion.
        assert state.error is not None

        # Multiple failures should have been recorded.
        assert len(state.failed_actions) >= 3

        # The LLM must have been called repeatedly,
        # but the agent must eventually stop.
        assert llm.calls >= 3

    finally:
        await manager.close()


class NoRepeatLLM:
    """
    Ensures the recovery decision is different from
    the failed action.
    """

    def __init__(self):
        self.calls = 0
        self.actions = []

    async def decide(
        self,
        task,
        observation,
        failure_feedback=None,
    ):
        self.calls += 1

        # First decision: intentionally fail.
        if self.calls == 1:
            action = BrowserAction(
                action="click",
                selector="#invalid",
                reason="Intentional failure",
            )

        # Second decision: recover using navigation.
        else:
            action = BrowserAction(
                action="navigate",
                url="https://example.com",
                reason="Use an alternate recovery action",
            )

        self.actions.append(action)

        return action


@pytest.mark.asyncio
async def test_recovery_does_not_repeat_failed_action():
    """
    Verify that the LLM is given an opportunity to choose
    an alternate action rather than blindly replaying the
    failed action.
    """

    manager = BrowserManager(headless=True)

    try:
        page = await manager.start()

        tools = BrowserTools(page)
        perception = Perception(tools)
        executor = ActionExecutor(tools)
        llm = NoRepeatLLM()

        agent = BrowserAgent(
            llm=llm,
            perception=perception,
            executor=executor,
            max_steps=3,
            max_action_retries=2,
        )

        state = await agent.run(
            "Open example.com"
        )

        # At least two decisions are required:
        # failed click + recovery navigation.
        assert len(llm.actions) >= 2

        first_action = llm.actions[0]
        second_action = llm.actions[1]

        # Verify the first action was the intentional failure.
        assert first_action.action == "click"
        assert first_action.selector == "#invalid"

        # Verify the second action is different.
        assert second_action.action == "navigate"
        assert second_action.url == "https://example.com"

        # The first action must have failed.
        assert len(state.failed_actions) >= 1

    finally:
        await manager.close()