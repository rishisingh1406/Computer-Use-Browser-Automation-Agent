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
        """
        Generate and validate a high-level browser plan.

        The planner is deliberately constrained to three
        high-level actions:

            navigate -> search -> extract

        Low-level browser operations are handled elsewhere.
        """

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
        # System prompt
        #
        # IMPORTANT:
        # Keep the JSON schema extremely simple.
        #
        # Groq's json_object mode can reject generation when
        # the model fails to produce a valid JSON object.
        # ------------------------------------------------------

        system_prompt = """
You are a high-level browser task planner.

Your job is to convert the user's goal into the smallest
reliable sequence of high-level browser subtasks for ONE website.

You decide WHAT needs to happen, not HOW the browser performs it.

Allowed actions:

- navigate
- search
- extract

Never use:

- click
- type
- scroll
- screenshot
- selector
- wait
- done

Planning rules:

1. Use sequential step_id values starting at 1.
2. Use only navigate, search, and extract.
3. Start with navigate when the website must be opened.
4. Use search when information must be located.
5. Use extract for the requested final information.
6. For information retrieval, extract must be the final step.
7. Keep the plan as small as reliably possible.
8. Do not describe low-level browser operations.
9. Do not invent website information.
10. Preserve the supplied goal exactly.
11. Preserve the supplied site exactly.
12. Every step must have a useful description.
13. target identifies the relevant page or information.
14. expected_result describes the successful outcome.
15. Return exactly one JSON object.
16. Do not return markdown.
17. Do not return explanations.
18. Do not return code fences.

The JSON object must have this structure:

{
  "goal": "the supplied goal",
  "site": "the supplied site",
  "steps": [
    {
      "step_id": 1,
      "action": "navigate",
      "description": "open the website",
      "target": "the supplied website",
      "expected_result": "the website is open"
    }
  ]
}
""".strip()

        # ------------------------------------------------------
        # User prompt
        # ------------------------------------------------------

        user_prompt = (
            f"WEBSITE:\n{site}\n\n"
            f"USER GOAL:\n{goal}\n\n"
            "Create the smallest reliable high-level plan "
            "required to accomplish this goal on this website.\n\n"
            "For information retrieval, normally use:\n"
            "navigate -> search -> extract\n\n"
            "Only include necessary steps.\n\n"
            "Return exactly one JSON object."
        )

        # ------------------------------------------------------
        # Call LLM
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

        data = self._parse_json(
            content
        )

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
    # PARSE JSON
    # ==========================================================

    @staticmethod
    def _parse_json(
        content: str,
    ) -> dict:
        """
        Parse planner JSON safely.

        Handles:
            1. normal JSON
            2. accidental markdown code fences
            3. surrounding whitespace

        Does not attempt to invent or repair planner data.
        """

        cleaned = content.strip()

        # ------------------------------------------------------
        # First attempt: direct JSON
        # ------------------------------------------------------

        try:
            data = json.loads(
                cleaned
            )

            if not isinstance(data, dict):
                raise ValueError(
                    "Planner response must be a JSON object."
                )

            return data

        except json.JSONDecodeError:
            pass

        # ------------------------------------------------------
        # Second attempt: remove markdown code fences
        # ------------------------------------------------------

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

        cleaned = cleaned.strip()

        try:
            data = json.loads(
                cleaned
            )

            if not isinstance(data, dict):
                raise ValueError(
                    "Planner response must be a JSON object."
                )

            return data

        except json.JSONDecodeError as exc:
            raise ValueError(
                "Groq returned invalid planner JSON:\n"
                f"{content}"
            ) from exc

    # ==========================================================
    # GROQ COMPLETION WITH RETRIES
    # ==========================================================

    async def _create_completion(
        self,
        system_prompt: str,
        user_prompt: str,
    ):
        """
        Call Groq with controlled retry handling.

        Retries are performed for rate limiting.

        JSON validation errors are not retried because they are
        request-generation failures rather than temporary
        transport/rate-limit failures.
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
                # Detect Groq rate limit
                # --------------------------------------------------

                if self._is_rate_limit_error(
                    exc
                ):

                    if attempt >= self.MAX_RETRIES:
                        raise RuntimeError(
                            "Planner LLM request failed after "
                            f"{self.MAX_RETRIES + 1} attempts "
                            "because of Groq rate limiting: "
                            f"{exc}"
                        ) from exc

                    delay = self._extract_retry_delay(
                        exc
                    )

                    # Progressive backoff.
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

                    continue

                # --------------------------------------------------
                # Non-rate-limit error
                # --------------------------------------------------

                raise RuntimeError(
                    f"Planner LLM request failed: {exc}"
                ) from exc

        # ------------------------------------------------------
        # Should never be reached.
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Direct status code
        # ------------------------------------------------------

        status_code = getattr(
            exc,
            "status_code",
            None,
        )

        if status_code == 429:
            return True

        # ------------------------------------------------------
        # Nested response status code
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Message fallback
        # ------------------------------------------------------

        message = str(
            exc
        ).lower()

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

        Supports examples such as:

            Please try again in 420ms.

        or:

            Please try again in 2s.

        Returns:
            delay in seconds.
        """

        message = str(
            exc
        )

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
                float(
                    match.group(1)
                ),
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
        """
        Validate the planner output beyond Pydantic validation.

        This protects the execution layer from malformed or
        logically unsafe plans.
        """

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
        # Allowed actions
        # ------------------------------------------------------

        allowed_actions = {
            "navigate",
            "search",
            "extract",
        }

        # ------------------------------------------------------
        # Validate each step
        # ------------------------------------------------------

        for step in plan.steps:

            if step.action not in allowed_actions:
                raise ValueError(
                    f"Step {step.step_id} uses invalid "
                    f"action: {step.action}"
                )

            # --------------------------------------------------
            # Description
            # --------------------------------------------------

            if not step.description.strip():
                raise ValueError(
                    f"Step {step.step_id} has no description."
                )

            # --------------------------------------------------
            # Target
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
            # Expected result
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

            last_index = (
                len(plan.steps) - 1
            )

            if extract_indexes[-1] != last_index:
                raise ValueError(
                    "The extract step must be the "
                    "final step of the plan."
                )