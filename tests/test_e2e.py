import os

import pytest

from app.agent.executor import ActionExecutor
from app.agent.llm import GroqBrowserLLM
from app.agent.loop import BrowserAgent
from app.agent.perception import Perception
from app.agent.plan_runner import PlanRunner
from app.agent.planner import PerSitePlanner
from app.browser.manager import BrowserManager
from app.browser.tools import BrowserTools


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not configured",
)
async def test_end_to_end_browser_plan():

    manager = BrowserManager(
        headless=False
    )

    try:
        # ======================================================
        # 1. Start browser
        # ======================================================

        page = await manager.start()

        # ======================================================
        # 2. Create browser tools
        # ======================================================

        browser_tools = BrowserTools(page)

        # ======================================================
        # 3. Create perception layer
        # ======================================================

        perception = Perception(
            browser_tools
        )

        # ======================================================
        # 4. Create action executor
        # ======================================================

        executor = ActionExecutor(
            browser_tools
        )

        # ======================================================
        # 5. Create low-level browser LLM
        # ======================================================

        llm = GroqBrowserLLM()

        # ======================================================
        # 6. Create browser agent
        # ======================================================

        browser_agent = BrowserAgent(
            llm=llm,
            perception=perception,
            executor=executor,
            max_steps=10,
        )

        # ======================================================
        # 7. Create high-level planner
        # ======================================================

        planner = PerSitePlanner()

        # ======================================================
        # 8. Generate plan
        # ======================================================

        plan = await planner.plan(
            goal="Get the title and main text from the website",
            site="https://example.com",
        )

        print("\n" + "=" * 70)
        print("GENERATED PLAN")
        print("=" * 70)

        for step in plan.steps:
            print(
                f"{step.step_id}. "
                f"[{step.action}] "
                f"{step.description}"
            )

        # ======================================================
        # 9. Create plan runner
        # ======================================================

        runner = PlanRunner(
            browser_agent=browser_agent
        )

        # ======================================================
        # 10. Execute complete plan
        # ======================================================

        result = await runner.run(
            plan
        )

        # ======================================================
        # 11. Validate result
        # ======================================================

        print("\n" + "=" * 70)
        print("FINAL E2E RESULT")
        print("=" * 70)

        print(result.model_dump())

        assert result.completed is True

        assert len(result.steps) == len(
            plan.steps
        )

        assert result.final_result is not None

    finally:
        # ======================================================
        # 12. Always close browser
        # ======================================================

        await manager.close()