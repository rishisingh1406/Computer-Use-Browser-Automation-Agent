from app.agent.loop import BrowserAgent
from app.agent.models import (
    BrowserPlan,
    PlanRunResult,
    PlanStep,
    PlanStepResult,
)
from app.auth.handler import SecureLoginHandler


class PlanRunner:
    """
    Executes a high-level BrowserPlan.

    Architecture:

        PerSitePlanner
              ↓
        BrowserPlan
              ↓
        PlanRunner
          /        \
         /          \
    normal step    login step
        ↓              ↓
    BrowserAgent   SecureLoginHandler
        ↓              ↓
    ActionExecutor  CredentialProvider
        ↓              ↓
    BrowserTools   LoginExecutor
                       ↓
                  BrowserTools

    Security boundary:

        Login credentials NEVER enter:

            - BrowserAction
            - BrowserAgent
            - LLM prompts
            - LLM responses
            - BrowserObservation
            - AgentState
            - PlanStep
            - PlanRunResult
    """

    def __init__(
        self,
        browser_agent: BrowserAgent,
        login_handler: SecureLoginHandler,
    ):
        self.browser_agent = browser_agent
        self.login_handler = login_handler

    async def run(
        self,
        plan: BrowserPlan,
    ) -> PlanRunResult:
        """
        Execute all high-level plan steps sequentially.

        Login steps are handled exclusively by the trusted
        authentication layer.
        """

        self._validate_plan(plan)

        results: list[PlanStepResult] = []

        print()
        print("=" * 70)
        print("EXECUTING BROWSER PLAN")
        print("=" * 70)
        print(f"Goal: {plan.goal}")
        print(f"Site: {plan.site}")
        print(f"Steps: {len(plan.steps)}")

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

            result = await self._run_step(
                step=step,
                site=plan.site,
            )

            results.append(result)

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

        final_result = self._build_final_result(
            results
        )

        print()
        print("=" * 70)
        print("BROWSER PLAN COMPLETED")
        print("=" * 70)
        print(
            f"Result: {final_result}"
        )

        return PlanRunResult(
            goal=plan.goal,
            site=plan.site,
            completed=True,
            steps=results,
            final_result=final_result,
        )

    @staticmethod
    def _validate_plan(
        plan: BrowserPlan,
    ) -> None:
        """
        Validate execution-specific plan invariants.
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

    async def _run_step(
        self,
        step: PlanStep,
        site: str,
    ) -> PlanStepResult:

        if step.action == "login":
            return await self._run_login_step(
                step=step,
                site=site,
            )

        return await self._run_browser_step(
            step=step,
        )

    async def _run_browser_step(
        self,
        step: PlanStep,
    ) -> PlanStepResult:
        """
        Execute navigate/search/extract using BrowserAgent.

        Credentials are never passed here.
        """

        task = self._build_subtask(step)

        print()
        print("Running browser agent...")

        try:
            state = await self.browser_agent.run(
                task
            )

        except Exception:
            print(
                "\nSTEP ERROR: Browser agent execution failed."
            )

            return PlanStepResult(
                step_id=step.step_id,
                action=step.action,
                description=step.description,
                finished=False,
                error="Browser agent execution failed.",
            )

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

            if step.action == "extract":
                extracted_text = getattr(
                    observation,
                    "text",
                    None,
                )

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

    async def _run_login_step(
        self,
        step: PlanStep,
        site: str,
    ) -> PlanStepResult:
        """
        Execute authentication through SecureLoginHandler.

        No credential material enters this method.
        """

        print()
        print("Running secure login handler...")

        try:
            await self.login_handler.login(
                site=site,
            )

            print(
                "Secure login completed."
            )

            return PlanStepResult(
                step_id=step.step_id,
                action=step.action,
                description=step.description,
                finished=True,
            )

        except Exception:
            print(
                "Secure login failed."
            )

            return PlanStepResult(
                step_id=step.step_id,
                action=step.action,
                description=step.description,
                finished=False,
                error="Secure login execution failed.",
            )

    @staticmethod
    def _build_subtask(
        step: PlanStep,
    ) -> str:
        """
        Convert a high-level PlanStep into a BrowserAgent task.

        Login steps never reach this method.
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

8. Never request, invent, infer, or expose
   authentication credentials.

9. If the site requires authentication and the
   current subtask cannot proceed without it,
   report that authentication is required.

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

    @staticmethod
    def _build_final_result(
        results: list[PlanStepResult],
    ) -> str | None:

        if not results:
            return None

        for result in reversed(results):
            if (
                result.action == "extract"
                and result.finished
                and result.extracted_text
            ):
                return result.extracted_text

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