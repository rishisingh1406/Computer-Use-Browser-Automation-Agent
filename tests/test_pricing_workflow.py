import os

import pytest

from app.agent.executor import ActionExecutor
from app.agent.llm import GroqBrowserLLM
from app.agent.loop import BrowserAgent
from app.agent.perception import Perception
from app.agent.planner import PerSitePlanner
from app.browser.manager import BrowserManager
from app.browser.tools import BrowserTools
from app.extraction.schemas import PricingTable
from app.workflows.pricing import PricingWorkflow


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not configured",
)
async def test_day_96_pricing_workflow():

    manager = BrowserManager(
        headless=False
    )

    try:

        # ==================================================
        # 1. Start browser
        # ==================================================

        page = await manager.start()

        # ==================================================
        # 2. Browser tools
        # ==================================================

        browser_tools = BrowserTools(
            page
        )

        # ==================================================
        # 3. Perception
        # ==================================================

        perception = Perception(
            browser_tools
        )

        # ==================================================
        # 4. Action executor
        # ==================================================

        executor = ActionExecutor(
            browser_tools
        )

        # ==================================================
        # 5. Browser LLM
        # ==================================================

        llm = GroqBrowserLLM()

        # ==================================================
        # 6. Low-level browser agent
        # ==================================================

        browser_agent = BrowserAgent(
            llm=llm,
            perception=perception,
            executor=executor,
            max_steps=12,
        )

        # ==================================================
        # 7. High-level planner
        # ==================================================

        planner = PerSitePlanner()

        # ==================================================
        # 8. Complete pricing workflow
        # ==================================================

        workflow = PricingWorkflow(
            planner=planner,
            browser_agent=browser_agent,
        )

        result = await workflow.run(
            goal="Get GitHub Copilot pricing",
            site="https://github.com",
            product="GitHub Copilot",
        )

        # ==================================================
        # 9. Validate normalized schema
        # ==================================================

        assert isinstance(
            result,
            PricingTable,
        )

        assert (
            result.site
            == "https://github.com"
        )

        assert (
            result.product
            == "GitHub Copilot"
        )

        assert isinstance(
            result.plans,
            list,
        )

        # ==================================================
        # 10. Print normalized result
        # ==================================================

        print("\n")
        print("=" * 70)
        print("DAY 96 PRICING RESULT")
        print("=" * 70)

        print(
            result.model_dump_json(
                indent=2
            )
        )

        # ==================================================
        # 11. Basic extraction sanity check
        # ==================================================

        assert len(result.plans) > 0

        for plan in result.plans:

            assert plan.name.strip()

            if plan.price is not None:
                assert plan.price >= 0

    finally:

        # ==================================================
        # 12. Always close browser
        # ==================================================

        await manager.close()