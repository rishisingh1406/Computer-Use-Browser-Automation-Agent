from app.agent.loop import BrowserAgent
from app.agent.plan_runner import PlanRunner
from app.agent.planner import PerSitePlanner
from app.extraction.pricing import PricingExtractor
from app.extraction.schemas import PricingTable


class PricingWorkflow:
    """
    End-to-end pricing extraction workflow.

    Architecture:

        User Goal
            |
            v
        PerSitePlanner
            |
            v
        BrowserPlan
            |
            v
        PlanRunner
            |
            v
        BrowserAgent
            |
            v
        BrowserTools / Playwright
            |
            v
        Final Browser Observation
            |
            v
        PricingExtractor
            |
            v
        PricingTable

    The planner decides WHAT needs to happen.

    The browser agent decides HOW to perform each
    high-level step.

    PricingExtractor deterministically converts the
    resulting page text into a normalized schema.
    """

    def __init__(
        self,
        planner: PerSitePlanner,
        browser_agent: BrowserAgent,
    ):
        self.planner = planner
        self.browser_agent = browser_agent
        self.extractor = PricingExtractor()

    async def run(
        self,
        goal: str,
        site: str,
        product: str | None = None,
    ) -> PricingTable:
        """
        Execute the complete pricing extraction workflow.
        """

        # ======================================================
        # 1. Generate high-level browser plan
        # ======================================================

        plan = await self.planner.plan(
            goal=goal,
            site=site,
        )

        # ======================================================
        # 2. Execute browser plan
        # ======================================================

        runner = PlanRunner(
            browser_agent=self.browser_agent,
        )

        result = await runner.run(
            plan
        )

        # ======================================================
        # 3. Fail if browser workflow failed
        # ======================================================

        if not result.completed:

            raise RuntimeError(
                "Pricing workflow failed: "
                f"{result.final_result or 'unknown error'}"
            )

        # ======================================================
        # 4. Find successful extraction result
        # ======================================================

        extracted_text = None

        for step_result in reversed(
            result.steps
        ):
            if (
                step_result.action == "extract"
                and step_result.finished
                and step_result.extracted_text
            ):
                extracted_text = (
                    step_result.extracted_text
                )
                break

        # ======================================================
        # 5. Validate extraction output
        # ======================================================

        if not extracted_text:
            raise RuntimeError(
                "Pricing workflow completed, "
                "but no page text was returned "
                "by the final extraction step."
            )

        # ======================================================
        # 6. Normalize pricing
        # ======================================================

        return self.extractor.extract(
            site=site,
            product=product,
            text=extracted_text,
        )