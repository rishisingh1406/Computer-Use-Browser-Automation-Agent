from app.agent.executor import ActionExecutor
from app.agent.llm import GroqBrowserLLM
from app.agent.models import AgentState
from app.agent.perception import Perception


class BrowserAgent:

    def __init__(
        self,
        llm: GroqBrowserLLM,
        perception: Perception,
        executor: ActionExecutor,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.perception = perception
        self.executor = executor
        self.max_steps = max_steps

    async def run(
        self,
        task: str,
    ) -> AgentState:

        state = AgentState(
            task=task
        )

        for step in range(
            1,
            self.max_steps + 1,
        ):

            state.step = step

            # ==================================================
            # OBSERVE
            # ==================================================

            observation = (
                await self.perception.observe()
            )

            state.observation = observation

            # ==================================================
            # DECIDE
            # ==================================================

            action = await self.llm.decide(
                task=task,
                observation=observation,
            )

            state.last_action = action

            # ==================================================
            # DEBUG
            # ==================================================

            print()
            print("=" * 60)
            print(
                f"BROWSER STEP {step}"
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

            # ==================================================
            # DONE
            # ==================================================

            if action.action == "done":

                state.finished = True

                print(
                    "Browser task completed."
                )

                break

            # ==================================================
            # EXECUTE
            # ==================================================

            try:

                result = await self.executor.execute(
                    action
                )

                # ----------------------------------------------
                # Preserve executor result
                # ----------------------------------------------

                state.last_result = result

                print(
                    "\nEXECUTOR RESULT:"
                )

                print(result)

            except Exception as exc:

                state.error = str(exc)

                print(
                    "\nBROWSER ACTION FAILED:"
                )

                print(exc)

                break

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