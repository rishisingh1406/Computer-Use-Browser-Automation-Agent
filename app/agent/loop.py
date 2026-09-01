from app.agent.executor import ActionExecutor
from app.agent.llm import GroqBrowserLLM
from app.agent.models import (
    AgentState,
    BrowserAction,
)
from app.agent.perception import Perception


class BrowserAgent:
    """
    Autonomous browser perception-action loop.

    Architecture:

        Observe
           ↓
        Decide
           ↓
        Execute
           ↓
       success?
        /    \
      yes     no
       ↓      ↓
     next   re-observe
              ↓
          re-decide
              ↓
        alternate action

    Day 100:
        Adds bounded retry and self-correction.

    Important:
        Retries do NOT blindly repeat the same action.
        Every recovery attempt gets a fresh observation and
        sends failure feedback to the LLM.
    """

    MAX_ACTION_RETRIES = 2

    def __init__(
        self,
        llm: GroqBrowserLLM,
        perception: Perception,
        executor: ActionExecutor,
        max_steps: int = 10,
        max_action_retries: int = MAX_ACTION_RETRIES,
    ):

        if max_steps < 1:
            raise ValueError(
                "max_steps must be at least 1."
            )

        if max_action_retries < 0:
            raise ValueError(
                "max_action_retries cannot be negative."
            )

        self.llm = llm
        self.perception = perception
        self.executor = executor
        self.max_steps = max_steps
        self.max_action_retries = (
            max_action_retries
        )

    # ==========================================================
    # ACTION DESCRIPTION
    # ==========================================================

    @staticmethod
    def _describe_action(
        action: BrowserAction,
    ) -> str:

        details = [
            f"action={action.action}"
        ]

        if action.selector:
            details.append(
                f"selector={action.selector}"
            )

        if action.url:
            details.append(
                f"url={action.url}"
            )

        if action.direction:
            details.append(
                f"direction={action.direction}"
            )

        return ", ".join(details)

    # ==========================================================
    # FAILURE FEEDBACK
    # ==========================================================

    @staticmethod
    def _build_failure_feedback(
        action: BrowserAction,
        error: Exception,
        retry_number: int,
        failed_actions: list[str],
    ) -> str:

        failed_action = (
            BrowserAgent._describe_action(
                action
            )
        )

        previous_failures = "\n".join(
            f"- {item}"
            for item in failed_actions
        )

        return f"""
The previous browser action failed.

Failed action:
{failed_action}

Execution error:
{error}

Recovery attempt:
{retry_number}

Previously failed actions:
{previous_failures}

You now have a NEW browser observation.

Do not blindly repeat the failed action.

Re-perceive the page and choose an alternate
grounded action or selector that can accomplish
the current subtask.

Do not assume that the previous selector is valid.
""".strip()

    # ==========================================================
    # RUN
    # ==========================================================

    async def run(
        self,
        task: str,
    ) -> AgentState:

        task = task.strip()

        if not task:
            raise ValueError(
                "Browser task cannot be empty."
            )

        state = AgentState(
            task=task
        )

        failure_feedback: str | None = None

        # ------------------------------------------------------
        # Planner-level browser steps
        # ------------------------------------------------------

        for step in range(
            1,
            self.max_steps + 1,
        ):

            state.step = step

            # Reset retry count for this browser step.
            state.retry_count = 0

            # ==================================================
            # SELF-CORRECTION LOOP
            # ==================================================

            while True:

                # ==============================================
                # OBSERVE
                # ==============================================

                try:

                    observation = (
                        await self.perception.observe()
                    )

                    state.observation = observation

                except Exception as exc:

                    state.error = (
                        "Browser perception failed: "
                        f"{exc}"
                    )

                    print()
                    print(
                        "BROWSER PERCEPTION FAILED:"
                    )
                    print(exc)

                    return state

                # ==============================================
                # DECIDE
                # ==============================================

                try:

                    action = await self.llm.decide(
                        task=task,
                        observation=observation,
                        failure_feedback=failure_feedback,
                    )

                except Exception as exc:

                    state.error = (
                        "Browser LLM decision failed: "
                        f"{exc}"
                    )

                    print()
                    print(
                        "BROWSER LLM DECISION FAILED:"
                    )
                    print(exc)

                    return state

                state.last_action = action

                # ==============================================
                # DEBUG
                # ==============================================

                print()
                print("=" * 60)

                if state.retry_count == 0:
                    print(
                        f"BROWSER STEP {step}"
                    )
                else:
                    print(
                        f"BROWSER STEP {step} "
                        f"RECOVERY {state.retry_count}/"
                        f"{self.max_action_retries}"
                    )

                print("=" * 60)

                print(
                    f"Observation URL: "
                    f"{observation.url}"
                )

                print(
                    f"Action: "
                    f"{action.action}"
                )

                print(
                    f"Reason: "
                    f"{action.reason}"
                )

                if failure_feedback:
                    print()
                    print(
                        "SELF-CORRECTION ACTIVE"
                    )

                # ==============================================
                # DONE
                # ==============================================

                if action.action == "done":

                    state.finished = True
                    state.error = None

                    print()
                    print(
                        "Browser task completed."
                    )

                    return state

                # ==============================================
                # EXECUTE
                # ==============================================

                try:

                    result = (
                        await self.executor.execute(
                            action
                        )
                    )

                    state.last_result = result

                    # Successful execution clears the
                    # recovery state.

                    state.error = None
                    state.retry_count = 0
                    failure_feedback = None

                    print()
                    print(
                        "EXECUTOR RESULT:"
                    )
                    print(result)

                    # ------------------------------------------
                    # Move to next browser step.
                    # ------------------------------------------

                    break

                except Exception as exc:

                    state.retry_count += 1

                    failed_action = (
                        self._describe_action(
                            action
                        )
                    )

                    state.failed_actions.append(
                        failed_action
                    )

                    state.error = str(exc)

                    print()
                    print(
                        "BROWSER ACTION FAILED:"
                    )
                    print(exc)

                    print()
                    print(
                        "SELF-CORRECTION"
                    )

                    print(
                        f"Recovery attempt: "
                        f"{state.retry_count}/"
                        f"{self.max_action_retries}"
                    )

                    # ------------------------------------------
                    # Retry budget exhausted
                    # ------------------------------------------

                    if (
                        state.retry_count
                        > self.max_action_retries
                    ):

                        print()
                        print(
                            "BROWSER ACTION FAILED "
                            "AFTER RECOVERY ATTEMPTS."
                        )

                        return state

                    # ------------------------------------------
                    # Build feedback for the next LLM decision.
                    # ------------------------------------------

                    failure_feedback = (
                        self._build_failure_feedback(
                            action=action,
                            error=exc,
                            retry_number=state.retry_count,
                            failed_actions=state.failed_actions,
                        )
                    )

                    print()
                    print(
                        "Re-perceiving browser state "
                        "and selecting an alternate action..."
                    )

                    # ------------------------------------------
                    # IMPORTANT:
                    #
                    # We do NOT break here.
                    #
                    # The while loop starts again:
                    #
                    # observe
                    #    ↓
                    # decide
                    #    ↓
                    # execute
                    #
                    # This gives the agent a fresh screenshot
                    # and fresh DOM observation.
                    # ------------------------------------------

        # ======================================================
        # MAX STEP FAILURE
        # ======================================================

        if not state.finished and not state.error:

            state.error = (
                f"Browser agent reached maximum "
                f"steps ({self.max_steps}) "
                f"without completing the task."
            )

            print()
            print(
                "BROWSER AGENT STOPPED: "
                "maximum steps reached."
            )

        return state