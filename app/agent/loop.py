from app.agent.executor import ActionExecutor
from app.agent.llm import BrowserDecisionLLM
from app.agent.models import AgentState
from app.agent.perception import Perception


class BrowserAgent:

    def __init__(
        self,
        llm: BrowserDecisionLLM,
        perception: Perception,
        executor: ActionExecutor,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.perception = perception
        self.executor = executor
        self.max_steps = max_steps

    async def run(self, task: str) -> AgentState:

        state = AgentState(task=task)

        for step in range(1, self.max_steps + 1):

            state.step = step

            observation = await self.perception.observe()

            state.observation = observation

            action = await self.llm.decide(
                task=task,
                observation=observation,
            )

            state.last_action = action

            print(f"Step {step}")
            print(f"Observation: {observation.url}")
            print(f"Action: {action.action}")
            print(f"Reason: {action.reason}")

            if action.action == "done":
                state.finished = True
                break

            await self.executor.execute(action)

        return state
