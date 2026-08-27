import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from app.agent.models import (
    BrowserAction,
    BrowserObservation,
)


load_dotenv()


class GroqBrowserLLM:
    """
    Low-level LLM used by BrowserAgent.

    Responsibility:
        Decide HOW to perform the current browser
        subtask.

    It does NOT create high-level BrowserPlans.

    High-level planning is handled by:
        PerSitePlanner

    This class only converts:

        BrowserObservation
                +
        Current subtask
                ↓
        BrowserAction
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
    # IMAGE ENCODING
    # ==========================================================

    def _encode_image(
        self,
        image_path: str,
    ) -> str:

        image_bytes = Path(
            image_path
        ).read_bytes()

        return base64.b64encode(
            image_bytes
        ).decode("utf-8")

    # ==========================================================
    # LOW-LEVEL BROWSER DECISION
    # ==========================================================

    async def decide(
        self,
        task: str,
        observation: BrowserObservation,
    ) -> BrowserAction:

        # ------------------------------------------------------
        # 1. Encode screenshot
        # ------------------------------------------------------

        image_data = self._encode_image(
            observation.screenshot_path
        )

        # ------------------------------------------------------
        # 2. System instructions
        # ------------------------------------------------------

        system_prompt = """
You are an autonomous browser automation agent.

Your job is to decide the NEXT browser action
required to complete the CURRENT SUBTASK.

You are operating inside a larger high-level
browser plan.

The high-level planner has already decided
WHAT needs to happen.

You are responsible only for deciding HOW
to perform the current subtask.

==================================================
ALLOWED ACTIONS
==================================================

You can choose ONLY ONE of:

1. navigate
2. click
3. type
4. scroll
5. done

Do not generate any other action.

==================================================
IMPORTANT
==================================================

Return ONLY a valid JSON object.

Do NOT return:

- markdown
- code fences
- explanations outside JSON
- reasoning outside JSON
- <think> tags

The JSON must always contain:

- action
- reason

==================================================
ACTION FORMATS
==================================================

For navigate:

{
    "action": "navigate",
    "url": "...",
    "reason": "..."
}

For click:

{
    "action": "click",
    "selector": "...",
    "reason": "..."
}

For type:

{
    "action": "type",
    "selector": "...",
    "text": "...",
    "reason": "..."
}

For scroll:

{
    "action": "scroll",
    "direction": "down",
    "reason": "..."
}

For a completed subtask:

{
    "action": "done",
    "reason": "..."
}

==================================================
DECISION RULES
==================================================

1. Choose exactly ONE action.

2. Use the current browser observation to
   determine the next action.

3. Use BOTH the screenshot and visible text.

4. Do not invent browser state.

5. Do not perform unrelated tasks.

6. Do not attempt the next high-level plan step.

7. Stop with "done" once the CURRENT SUBTASK
   has been successfully completed.

8. If the current subtask requires finding
   information, navigate/search using the
   available browser interface.

9. If the current subtask requires extracting
   information, stop once the requested
   information is visibly available.

10. Do not declare the subtask complete merely
    because a page has loaded if the requested
    information has not yet been located.

==================================================
LOW-LEVEL EXECUTION
==================================================

You may use:

- navigate
- click
- type
- scroll

to accomplish the current subtask.

The browser execution system will execute
your selected action.

After execution, you will receive a new
browser observation.

Continue until the current subtask is complete.

Return "done" only when it is actually complete.
"""

        # ------------------------------------------------------
        # 3. Current browser observation
        # ------------------------------------------------------

        user_prompt = f"""
CURRENT SUBTASK:

{task}

CURRENT BROWSER STATE:

URL:
{observation.url}

TITLE:
{observation.title}

VISIBLE TEXT:
{observation.text[:8000]}

The screenshot represents the current visual
browser state.

Use BOTH:

1. the screenshot
2. the visible browser text

Decide the single best NEXT browser action
for the current subtask.

Return ONLY the JSON object.
"""

        # ------------------------------------------------------
        # 4. Ask Groq
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
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        "data:image/png;base64,"
                                        + image_data
                                    )
                                },
                            },
                        ],
                    },
                ],
            )

        except Exception as exc:

            raise RuntimeError(
                f"Browser LLM request failed: {exc}"
            ) from exc

        # ------------------------------------------------------
        # 5. Extract response
        # ------------------------------------------------------

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:

            raise ValueError(
                "Groq returned an empty response."
            )

        print()
        print("--- GROQ BROWSER RESPONSE ---")
        print(content)

        # ------------------------------------------------------
        # 6. Parse JSON
        # ------------------------------------------------------

        try:

            data = json.loads(content)

        except json.JSONDecodeError as exc:

            raise ValueError(
                f"Groq returned invalid JSON: {content}"
            ) from exc

        # ------------------------------------------------------
        # 7. Validate BrowserAction
        # ------------------------------------------------------

        try:

            action = BrowserAction.model_validate(
                data
            )

        except Exception as exc:

            raise ValueError(
                "Groq returned an invalid browser action: "
                f"{data}"
            ) from exc

        return action