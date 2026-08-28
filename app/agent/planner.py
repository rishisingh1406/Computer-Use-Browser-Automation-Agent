
import asyncio
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from app.agent.models import (
    BrowserPlan,
    PlanStep,
)

load_dotenv()


class PerSitePlanner:
    """
    High-level planner for browser tasks.

    Responsibility:
        Decide WHAT needs to happen.

    It does NOT:
        - interact with the browser
        - choose CSS selectors
        - click elements
        - type text
        - scroll
        - execute browser actions

    Execution is handled by PlanRunner and BrowserAgent.
    """

    DEFAULT_MODEL = "qwen/qwen3.6-27b"

    MAX_RETRIES = 3

    # Used when Groq does not expose a retry delay directly.
    DEFAULT_RETRY_DELAY = 1.0

    def __init__(
        self,
        model: str | None = None,
    ):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set."
            )

        self.client = Groq(
            api_key=api_key
        )

        self.model = (
            model
            or os.getenv(
                "GROQ_PLANNER_MODEL"
            )
            or self.DEFAULT_MODEL
        )

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
        # Compact system prompt
        #
        # Keep this intentionally small.
        # Planner calls consume input TPM.
        # ------------------------------------------------------

        system_prompt = """
You are a high-level browser task planner.

Convert the user's goal into the smallest reliable
sequence of high-level browser subtasks for ONE website.

You decide WHAT must happen, not HOW the browser performs it.

Allowed actions:
- navigate: open the requested website or relevant page
- search: locate the requested information on the website
- extract: collect the requested information

Never use:
click, type, scroll, screenshot, selector, wait, done.

Rules:
1. Use sequential step_id values starting at 1.
2. Use only navigate, search, extract.
3. Start with navigate when the website must be opened.
4. Use search when information must be located.
5. Use extract for the requested final information.
6. Extract must be the final step for information-retrieval tasks.
7. Keep the plan as small as reliably possible.
8. Do not describe low-level browser operations.
9. Do not invent website information.
10. Preserve the supplied goal and site exactly.
11. Every step needs a useful description.
12. target identifies the relevant page or information.
13. expected_result describes the successful outcome.

Return ONLY valid JSON in this structure:

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
""".strip()

        # ------------------------------------------------------
        # User prompt
        # ------------------------------------------------------

        user_prompt = f"""
WEBSITE:
{site}

USER GOAL:
{goal}

Create the smallest reliable high-level plan required
to accomplish this goal on this website.

For information retrieval, normally use:
navigate -> search -> extract

Only include necessary steps.

Return ONLY the JSON object.
""".strip()

        # ------------------------------------------------------
        # Call LLM with retry handling
        # ------------------------------------------------------

        response = await self._create_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

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
        # Validate against BrowserPlan
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
    # GROQ COMPLETION WITH RATE-LIMIT RETRIES
    # ==========================================================

    async def _create_completion(
        self,
        system_prompt: str,
        user_prompt: str,
    ):
        """
        Call Groq with controlled retry handling.

        Groq can temporarily return HTTP 429 when the
        organization's TPM limit is exceeded.

        The retry delay is extracted from the error message
        when possible.
        """

        for attempt in range(
            self.MAX_RETRIES + 1
        ):

            try:

                return self.client.chat.completions.create(
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

                # --------------------------------------------------
                # Detect Groq 429 rate limit
                # --------------------------------------------------

                if not self._is_rate_limit_error(
                    exc
                ):
                    raise RuntimeError(
                        f"Planner LLM request failed: {exc}"
                    ) from exc

                # --------------------------------------------------
                # No retries remaining
                # --------------------------------------------------

                if attempt >= self.MAX_RETRIES:

                    raise RuntimeError(
                        "Planner LLM request failed after "
                        f"{self.MAX_RETRIES + 1} attempts "
                        f"because of Groq rate limiting: {exc}"
                    ) from exc

                # --------------------------------------------------
                # Determine retry delay
                # --------------------------------------------------

                delay = self._extract_retry_delay(
                    exc
                )

                # Add a small progressive backoff so that
                # repeated calls do not hammer the API.
                delay += attempt * 0.5

                print()
                print(
                    "PLANNER RATE LIMIT"
                )

                print(
                    f"Attempt: {attempt + 1}/"
                    f"{self.MAX_RETRIES + 1}"
                )

                print(
                    f"Retrying in {delay:.2f} seconds..."
                )

                await asyncio.sleep(
                    delay
                )

        # This should never be reached.
        raise RuntimeError(
            "Planner LLM request failed unexpectedly."
        )

    # ==========================================================
    # RATE LIMIT DETECTION
    # ==========================================================

    @staticmethod
    def _is_rate_limit_error(
        exc: Exception,
    ) -> bool:
        """
        Determine whether an exception represents
        a Groq HTTP 429 rate limit.
        """

        # Groq SDK exposes RateLimitError, but checking
        # the status code/message makes this resilient
        # across SDK versions.

        status_code = getattr(
            exc,
            "status_code",
            None,
        )

        if status_code == 429:
            return True

        response = getattr(
            exc,
            "response",
            None,
        )

        if response is not None:

            response_status = getattr(
                response,
                "status_code",
                None,
            )

            if response_status == 429:
                return True

        message = str(exc).lower()

        return (
            "rate limit" in message
            or "rate_limit" in message
            or "429" in message
            or "tokens per minute" in message
        )

    # ==========================================================
    # EXTRACT RETRY DELAY
    # ==========================================================

    @staticmethod
    def _extract_retry_delay(
        exc: Exception,
    ) -> float:
        """
        Extract retry delay from a Groq error.

        Example Groq message:

            Please try again in 420ms.

        Returns:
            delay in seconds.
        """

        message = str(exc)

        # ------------------------------------------------------
        # Milliseconds
        # ------------------------------------------------------

        match = re.search(
            r"try again in\s+(\d+(?:\.\d+)?)\s*ms",
            message,
            re.IGNORECASE,
        )

        if match:

            milliseconds = float(
                match.group(1)
            )

            return max(
                milliseconds / 1000.0,
                0.1,
            )

        # ------------------------------------------------------
        # Seconds
        # ------------------------------------------------------

        match = re.search(
            r"try again in\s+(\d+(?:\.\d+)?)\s*s",
            message,
            re.IGNORECASE,
        )

        if match:

            return max(
                float(match.group(1)),
                0.1,
            )

        # ------------------------------------------------------
        # Default
        # ------------------------------------------------------

        return PerSitePlanner.DEFAULT_RETRY_DELAY

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
        # Extract must be final
        # ------------------------------------------------------

        extract_indexes = [
            index
            for index, step in enumerate(
                plan.steps
            )
            if step.action == "extract"
        ]

        if extract_indexes:

            last_index = len(
                plan.steps
            ) - 1

            if extract_indexes[-1] != last_index:

                raise ValueError(
                    "The extract step must be the "
                    "final step of the plan."
                )

