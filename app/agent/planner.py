import json
import os

from dotenv import load_dotenv
from groq import Groq

from app.agent.models import (
    BrowserPlan,
    PlanStep,
)

load_dotenv()


class PerSitePlanner:
    """
    Generates a high-level browser execution plan
    for a specific website.

    Responsibility:
        Decide WHAT needs to happen.

    It does NOT:
        - interact with the browser
        - choose CSS selectors
        - click elements
        - type text
        - execute actions

    Execution is handled later by PlanRunner
    and BrowserAgent.
    """

    def __init__(
        self,
        model: str = "qwen/qwen3.6-27b",
    ):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set."
            )

        self.client = Groq(
            api_key=api_key
        )

        self.model = model

    # ==========================================================
    # GENERATE PLAN
    # ==========================================================

    async def plan(
        self,
        goal: str,
        site: str,
    ) -> BrowserPlan:

        # ------------------------------------------------------
        # Validate input
        # ------------------------------------------------------

        goal = goal.strip()
        site = site.strip()

        if not goal:
            raise ValueError(
                "goal cannot be empty"
            )

        if not site:
            raise ValueError(
                "site cannot be empty"
            )

        # ------------------------------------------------------
        # Planner system prompt
        # ------------------------------------------------------

        system_prompt = """
You are a high-level browser-agent task planner.

Your job is to convert a user's goal into a
small, reliable sequence of browser subtasks
for ONE specific website.

You are NOT executing the browser.

You are ONLY deciding WHAT needs to happen.

The resulting plan will be executed by:

PerSitePlanner
    ↓
BrowserPlan
    ↓
PlanRunner
    ↓
BrowserAgent
    ↓
Browser tools

==================================================
ALLOWED HIGH-LEVEL ACTIONS
==================================================

Every plan step MUST use exactly one of:

- navigate
- search
- extract

Do NOT use:

- click
- type
- scroll
- screenshot
- selector
- wait
- done

Those are low-level browser operations handled
by the BrowserAgent.

==================================================
PLANNING PRINCIPLES
==================================================

1. Start with navigation when the task requires
   opening the target website.

2. Use SEARCH when information must be located
   within the website.

3. Use EXTRACT when the requested information
   has been located and needs to be collected.

4. Keep subtasks small and independently
   understandable.

5. Each step must have one clear purpose.

6. Do not combine unrelated operations into one
   step.

7. Do not describe CSS selectors.

8. Do not describe mouse coordinates.

9. Do not specify click/type/scroll operations.

10. Do not invent information about the website.

11. Prefer the smallest reliable plan.

12. The final step should normally be EXTRACT
    for information-retrieval tasks.

==================================================
STEP DEFINITIONS
==================================================

NAVIGATE:

Open the requested website or relevant page.

SEARCH:

Locate the page, product, document, category,
or information requested by the user.

EXTRACT:

Read and return the specific information the
user requested.

==================================================
PLAN STRUCTURE
==================================================

Return ONLY valid JSON.

Do not return:

- markdown
- code fences
- explanations
- reasoning
- <think> tags

The JSON must have exactly this structure:

{
    "goal": "...",
    "site": "...",
    "steps": [
        {
            "step_id": 1,
            "action": "navigate",
            "description": "...",
            "target": "...",
            "expected_result": "..."
        }
    ]
}

==================================================
PLAN RULES
==================================================

1. step_id MUST start at 1.

2. step_id MUST increase sequentially.

3. Use only:
   navigate, search, extract

4. Every step MUST have a useful description.

5. target should identify the page, information,
   or destination relevant to that step.

6. expected_result should describe what successful
   completion of the step should produce.

7. Do not include low-level browser actions.

8. Do not include unnecessary steps.

9. Do not attempt to perform the user's goal.

10. Only describe the plan required to accomplish it.

11. Preserve the user's goal exactly in the
    "goal" field.

12. Preserve the requested website exactly in
    the "site" field.
"""

        # ------------------------------------------------------
        # User prompt
        # ------------------------------------------------------

        user_prompt = f"""
WEBSITE:
{site}

USER GOAL:
{goal}

Create the smallest reliable high-level browser
plan required to accomplish this goal on this
specific website.

For a typical information-retrieval task,
the plan may look like:

1. Navigate to the website.
2. Search for the requested information.
3. Extract the requested information.

Only include steps that are actually necessary.

Return ONLY the JSON object.
"""

        # ------------------------------------------------------
        # Call LLM
        # ------------------------------------------------------

        try:

            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={
                    "type": "json_object"
                },
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            )

        except Exception as exc:

            raise RuntimeError(
                f"Planner LLM request failed: {exc}"
            ) from exc

        # ------------------------------------------------------
        # Get response content
        # ------------------------------------------------------

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:
            raise ValueError(
                "Groq returned an empty planning response."
            )

        print()
        print("=" * 70)
        print("PLANNER RESPONSE")
        print("=" * 70)
        print(content)

        # ------------------------------------------------------
        # Parse JSON
        # ------------------------------------------------------

        try:

            data = json.loads(content)

        except json.JSONDecodeError as exc:

            raise ValueError(
                "Groq returned invalid planner JSON."
            ) from exc

        # ------------------------------------------------------
        # Validate against shared BrowserPlan model
        # ------------------------------------------------------

        try:

            plan = BrowserPlan.model_validate(
                data
            )

        except Exception as exc:

            raise ValueError(
                "Groq returned an invalid browser plan: "
                f"{data}"
            ) from exc

        # ------------------------------------------------------
        # Additional planner validation
        # ------------------------------------------------------

        self._validate_plan(
            plan=plan,
            goal=goal,
            site=site,
        )

        return plan

    # ==========================================================
    # VALIDATE PLAN
    # ==========================================================

    @staticmethod
    def _validate_plan(
        plan: BrowserPlan,
        goal: str,
        site: str,
    ) -> None:

        # ------------------------------------------------------
        # Goal validation
        # ------------------------------------------------------

        if plan.goal != goal:

            raise ValueError(
                "Planner returned an incorrect goal."
            )

        # ------------------------------------------------------
        # Site validation
        # ------------------------------------------------------

        if plan.site != site:

            raise ValueError(
                "Planner returned an incorrect site."
            )

        # ------------------------------------------------------
        # Empty plan validation
        # ------------------------------------------------------

        if not plan.steps:

            raise ValueError(
                "Planner returned an empty plan."
            )

        # ------------------------------------------------------
        # Step ID validation
        # ------------------------------------------------------

        expected_ids = list(
            range(
                1,
                len(plan.steps) + 1,
            )
        )

        actual_ids = [
            step.step_id
            for step in plan.steps
        ]

        if actual_ids != expected_ids:

            raise ValueError(
                "Planner step IDs must be sequential "
                "starting from 1."
            )

        # ------------------------------------------------------
        # Step validation
        # ------------------------------------------------------

        allowed_actions = {
            "navigate",
            "search",
            "extract",
        }

        for step in plan.steps:

            if step.action not in allowed_actions:

                raise ValueError(
                    f"Step {step.step_id} uses invalid "
                    f"action: {step.action}"
                )

            if not step.description.strip():

                raise ValueError(
                    f"Step {step.step_id} has no description."
                )

            # --------------------------------------------------
            # Target validation
            # --------------------------------------------------

            if step.action in {
                "navigate",
                "search",
            }:
                if (
                    step.target is not None
                    and not step.target.strip()
                ):
                    raise ValueError(
                        f"Step {step.step_id} has "
                        "an empty target."
                    )

            # --------------------------------------------------
            # Expected result validation
            # --------------------------------------------------

            if (
                step.expected_result is not None
                and not step.expected_result.strip()
            ):
                raise ValueError(
                    f"Step {step.step_id} has "
                    "an empty expected_result."
                )

        # ------------------------------------------------------
        # Information-retrieval plans should end with
        # extraction.
        #
        # We don't force every possible task to end
        # with extract, but if the plan contains an
        # extract step it should be the final step.
        # ------------------------------------------------------

        extract_indexes = [
            index
            for index, step in enumerate(plan.steps)
            if step.action == "extract"
        ]

        if extract_indexes:

            last_index = len(plan.steps) - 1

            if extract_indexes[-1] != last_index:

                raise ValueError(
                    "The extract step must be the "
                    "final step of the plan."
                )