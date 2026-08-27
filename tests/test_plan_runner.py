import pytest

from app.agent.models import (
    BrowserPlan,
    PlanStep,
)

from app.agent.plan_runner import PlanRunner


# ==========================================================
# FAKE BROWSER AGENT
# ==========================================================


class FakeAgent:

    def __init__(self):
        self.tasks = []

    async def run(self, task: str):

        self.tasks.append(task)

        class Observation:
            url = "https://example.com"
            title = "Example"
            text = "Example browser content"

        class Result:
            finished = True
            observation = Observation()
            error = None

        return Result()


# ==========================================================
# TEST PLAN
# ==========================================================


def make_plan() -> BrowserPlan:

    return BrowserPlan(
        goal="Get pricing",
        site="https://example.com",
        steps=[
            PlanStep(
                step_id=1,
                action="navigate",
                description="Navigate to the website",
                target="https://example.com",
                expected_result="Homepage loads",
            ),
            PlanStep(
                step_id=2,
                action="search",
                description="Find the pricing page",
                target="pricing",
                expected_result="Pricing page found",
            ),
            PlanStep(
                step_id=3,
                action="extract",
                description="Extract pricing information",
                target="pricing details",
                expected_result="Pricing extracted",
            ),
        ],
    )


# ==========================================================
# EXECUTE ALL STEPS
# ==========================================================


@pytest.mark.asyncio
async def test_plan_runner_executes_all_steps():

    fake_agent = FakeAgent()

    runner = PlanRunner(
        browser_agent=fake_agent
    )

    plan = make_plan()

    result = await runner.run(plan)

    # ------------------------------------------------------
    # Plan result
    # ------------------------------------------------------

    assert result.completed is True

    assert result.goal == "Get pricing"

    assert result.site == "https://example.com"

    assert len(result.steps) == 3

    # ------------------------------------------------------
    # Browser agent execution
    # ------------------------------------------------------

    assert len(fake_agent.tasks) == 3

    assert (
        "Navigate to the website"
        in fake_agent.tasks[0]
    )

    assert (
        "Find the pricing page"
        in fake_agent.tasks[1]
    )

    assert (
        "Extract pricing information"
        in fake_agent.tasks[2]
    )


# ==========================================================
# VERIFY HIGH-LEVEL ACTIONS
# ==========================================================


@pytest.mark.asyncio
async def test_plan_runner_preserves_step_actions():

    fake_agent = FakeAgent()

    runner = PlanRunner(
        browser_agent=fake_agent
    )

    plan = make_plan()

    result = await runner.run(plan)

    assert [
        step.action
        for step in result.steps
    ] == [
        "navigate",
        "search",
        "extract",
    ]


# ==========================================================
# STOP WHEN STEP FAILS
# ==========================================================


@pytest.mark.asyncio
async def test_plan_runner_stops_when_step_fails():

    class FailingAgent:

        def __init__(self):
            self.tasks = []

        async def run(self, task: str):

            self.tasks.append(task)

            class Result:
                finished = False
                observation = None
                error = "Subtask failed"

            return Result()

    fake_agent = FailingAgent()

    runner = PlanRunner(
        browser_agent=fake_agent
    )

    plan = make_plan()

    result = await runner.run(plan)

    # ------------------------------------------------------
    # Plan must fail
    # ------------------------------------------------------

    assert result.completed is False

    # ------------------------------------------------------
    # Only first step should execute
    # ------------------------------------------------------

    assert len(result.steps) == 1

    assert len(fake_agent.tasks) == 1

    # ------------------------------------------------------
    # Failure must be preserved
    # ------------------------------------------------------

    assert result.steps[0].finished is False

    assert result.steps[0].error == (
        "Subtask failed"
    )

    assert (
        "Plan failed at step 1"
        in result.final_result
    )


# ==========================================================
# HANDLE AGENT EXCEPTION
# ==========================================================


@pytest.mark.asyncio
async def test_plan_runner_handles_agent_exception():

    class ExceptionAgent:

        async def run(self, task: str):

            raise RuntimeError(
                "Browser crashed"
            )

    runner = PlanRunner(
        browser_agent=ExceptionAgent()
    )

    plan = make_plan()

    result = await runner.run(plan)

    assert result.completed is False

    assert len(result.steps) == 1

    assert result.steps[0].finished is False

    assert result.steps[0].error == (
        "Browser crashed"
    )


# ==========================================================
# EXTRACTION RESULT
# ==========================================================


@pytest.mark.asyncio
async def test_plan_runner_returns_extraction_result():

    class ExtractionAgent:

        def __init__(self):
            self.tasks = []

        async def run(self, task: str):

            self.tasks.append(task)

            class Observation:
                url = "https://example.com/pricing"
                title = "Pricing"
                text = (
                    "Basic: $10/month\n"
                    "Pro: $25/month"
                )

            class Result:
                finished = True
                observation = Observation()
                error = None

            return Result()

    fake_agent = ExtractionAgent()

    runner = PlanRunner(
        browser_agent=fake_agent
    )

    plan = make_plan()

    result = await runner.run(plan)

    assert result.completed is True

    assert result.final_result == (
        "Basic: $10/month\n"
        "Pro: $25/month"
    )

    assert result.steps[-1].extracted_text == (
        "Basic: $10/month\n"
        "Pro: $25/month"
    )


# ==========================================================
# INVALID STEP ORDER
# ==========================================================


@pytest.mark.asyncio
async def test_plan_runner_rejects_invalid_step_order():

    fake_agent = FakeAgent()

    runner = PlanRunner(
        browser_agent=fake_agent
    )

    plan = make_plan()

    plan.steps[1].step_id = 5

    with pytest.raises(ValueError):

        await runner.run(plan)

    # No browser task should have executed.

    assert len(fake_agent.tasks) == 0