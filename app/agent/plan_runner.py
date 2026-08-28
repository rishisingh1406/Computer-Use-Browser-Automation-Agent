
from app.agent.loop import BrowserAgent

from app.agent.models import (
    BrowserPlan,
    PlanRunResult,
    PlanStep,
    PlanStepResult,
)


class PlanRunner:
    """
    Executes a high-level BrowserPlan using BrowserAgent.

    Architecture:

        PerSitePlanner
              ↓
        BrowserPlan
              ↓
        PlanRunner
              ↓
        BrowserAgent
              ↓
        BrowserTools

    PerSitePlanner decides WHAT should happen.

    PlanRunner orchestrates the high-level steps.

    BrowserAgent decides HOW to perform each step.
    """

    def __init__(
        self,
        browser_agent: BrowserAgent,
    ):
        self.browser_agent = browser_agent

    # ==========================================================
    # RUN COMPLETE PLAN
    # ==========================================================

    async def run(
        self,
        plan: BrowserPlan,
    ) -> PlanRunResult:

        # ------------------------------------------------------
        # Validate before touching the browser
        # ------------------------------------------------------

        self._validate_plan(plan)

        results: list[PlanStepResult] = []

        print()
        print("=" * 70)
        print("EXECUTING BROWSER PLAN")
        print("=" * 70)

        print(f"Goal: {plan.goal}")
        print(f"Site: {plan.site}")
        print(f"Steps: {len(plan.steps)}")

        # ------------------------------------------------------
        # Execute steps sequentially
        # ------------------------------------------------------

        for index, step in enumerate(
            plan.steps,
            start=1,
        ):

            print()
            print("=" * 70)
            print(
                f"PLAN STEP {index}/{len(plan.steps)} "
                f"(ID: {step.step_id})"
            )
            print("=" * 70)

            print(f"Action: {step.action}")
            print(f"Description: {step.description}")

            if step.target:
                print(f"Target: {step.target}")

            if step.expected_result:
                print(
                    f"Expected: {step.expected_result}"
                )

            # --------------------------------------------------
            # Execute one high-level step
            # --------------------------------------------------

            result = await self._run_step(step)

            results.append(result)

            # --------------------------------------------------
            # Stop immediately on failure
            # --------------------------------------------------

            if not result.finished:

                print()
                print(
                    f"PLAN FAILED AT STEP "
                    f"{step.step_id}"
                )

                return PlanRunResult(
                    goal=plan.goal,
                    site=plan.site,
                    completed=False,
                    steps=results,
                    final_result=(
                        f"Plan failed at step "
                        f"{step.step_id}: "
                        f"{result.error or 'unknown error'}"
                    ),
                )

        # ------------------------------------------------------
        # Build final result
        # ------------------------------------------------------

        final_result = self._build_final_result(
            results
        )

        print()
        print("=" * 70)
        print("BROWSER PLAN COMPLETED")
        print("=" * 70)

        print(f"Result: {final_result}")

        return PlanRunResult(
            goal=plan.goal,
            site=plan.site,
            completed=True,
            steps=results,
            final_result=final_result,
        )

    # ==========================================================
    # VALIDATE PLAN
    # ==========================================================

    @staticmethod
    def _validate_plan(
        plan: BrowserPlan,
    ) -> None:
        """
        Validate structural properties required by PlanRunner.

        BrowserPlan already validates the Pydantic schema.

        This method validates execution-specific invariants.
        """

        if not plan.steps:
            raise ValueError(
                "Cannot execute an empty browser plan"
            )

        expected_step_id = 1

        for step in plan.steps:

            if step.step_id != expected_step_id:
                raise ValueError(
                    "Invalid plan step ordering: "
                    f"expected step_id "
                    f"{expected_step_id}, "
                    f"got {step.step_id}"
                )

            expected_step_id += 1

    # ==========================================================
    # RUN SINGLE PLAN STEP
    # ==========================================================

    async def _run_step(
        self,
        step: PlanStep,
    ) -> PlanStepResult:

        task = self._build_subtask(step)

        print()
        print("Running browser agent...")

        # ------------------------------------------------------
        # Execute browser agent
        # ------------------------------------------------------

        try:

            state = await self.browser_agent.run(
                task
            )

        except Exception as exc:

            print(
                f"\nSTEP ERROR: {exc}"
            )

            return PlanStepResult(
                step_id=step.step_id,
                action=step.action,
                description=step.description,
                finished=False,
                error=str(exc),
            )

        # ------------------------------------------------------
        # Extract final browser state
        # ------------------------------------------------------

        final_url = None
        final_title = None
        extracted_text = None

        observation = getattr(
            state,
            "observation",
            None,
        )

        if observation:

            final_url = getattr(
                observation,
                "url",
                None,
            )

            final_title = getattr(
                observation,
                "title",
                None,
            )

            # Only EXTRACT steps expose page text
            # as the extracted result.
            if step.action == "extract":

                extracted_text = getattr(
                    observation,
                    "text",
                    None,
                )

        # ------------------------------------------------------
        # Determine success
        # ------------------------------------------------------

        finished = getattr(
            state,
            "finished",
            False,
        )

        error = getattr(
            state,
            "error",
            None,
        )

        if not finished:

            return PlanStepResult(
                step_id=step.step_id,
                action=step.action,
                description=step.description,
                finished=False,
                final_url=final_url,
                final_title=final_title,
                extracted_text=extracted_text,
                error=(
                    error
                    or "Browser agent did not finish "
                       "the subtask"
                ),
            )

        # ------------------------------------------------------
        # Successful step
        # ------------------------------------------------------

        return PlanStepResult(
            step_id=step.step_id,
            action=step.action,
            description=step.description,
            finished=True,
            final_url=final_url,
            final_title=final_title,
            extracted_text=extracted_text,
            error=error,
        )

    # ==========================================================
    # BUILD SUBTASK
    # ==========================================================

    @staticmethod
    def _build_subtask(
        step: PlanStep,
    ) -> str:
        """
        Convert a high-level PlanStep into a task
        that BrowserAgent can execute.

        PlanRunner does not perform browser operations itself.
        """

        return f"""
You are executing ONE subtask of a larger
browser automation plan.

HIGH-LEVEL ACTION:
{step.action}

SUBTASK:
{step.description}

TARGET:
{step.target or "Not specified"}

EXPECTED RESULT:
{step.expected_result or "Not specified"}

IMPORTANT RULES:

1. Complete ONLY this subtask.
2. Do not perform unrelated actions.
3. Use the browser observation and available
   browser tools.
4. Continue until the requested subtask is
   actually complete.
5. When the subtask is complete, return the
   "done" action.
6. If the requested result cannot be found,
   clearly report the failure instead of
   pretending the task succeeded.
7. Do not attempt the next plan step.

ACTION-SPECIFIC INSTRUCTIONS:

NAVIGATE:
- Open the requested website or page.
- Verify that the destination has loaded.
- Stop once the destination is available.

SEARCH:
- Locate the requested information.
- Use the site's search or navigation interface
  when appropriate.
- Navigate to the most relevant page.
- Do not extract unrelated information.
- Stop once the relevant page or information
  has been located.

EXTRACT:
- Find the requested information.
- Read the relevant visible information.
- Capture the requested information from
  the page.
- Do not extract unrelated information.
- Stop once the requested information has
  been identified.

Remember:

You are responsible for HOW to accomplish
this subtask.

Do not attempt the next plan step.
"""

    # ==========================================================
    # BUILD FINAL RESULT
    # ==========================================================

    @staticmethod
    def _build_final_result(
        results: list[PlanStepResult],
    ) -> str | None:

        if not results:
            return None

        # ------------------------------------------------------
        # Prefer successful extraction
        # ------------------------------------------------------

        for result in reversed(results):

            if (
                result.action == "extract"
                and result.finished
                and result.extracted_text
            ):
                return result.extracted_text

        # ------------------------------------------------------
        # No extraction step
        #
        # Return useful information about the final
        # successful browser state.
        # ------------------------------------------------------

        last_result = results[-1]

        if not last_result.finished:
            return None

        if last_result.extracted_text:
            return last_result.extracted_text

        if last_result.final_title:
            return (
                f"Completed at: "
                f"{last_result.final_title}"
            )

        if last_result.final_url:
            return (
                f"Completed at: "
                f"{last_result.final_url}"
            )

        return None

