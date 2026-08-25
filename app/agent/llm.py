import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from app.agent.models import BrowserAction, BrowserObservation


load_dotenv()


class GroqBrowserLLM:
    def __init__(
        self,
        model: str = "qwen/qwen3.6-27b",
    ):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set."
            )

        self.client = Groq(api_key=api_key)
        self.model = model

    def _encode_image(
        self,
        image_path: str,
    ) -> str:
        image_bytes = Path(image_path).read_bytes()

        return base64.b64encode(
            image_bytes
        ).decode("utf-8")

    async def decide(
        self,
        task: str,
        observation: BrowserObservation,
    ) -> BrowserAction:

        # --------------------------------------------------
        # 1. Encode current browser screenshot
        # --------------------------------------------------

        image_data = self._encode_image(
            observation.screenshot_path
        )

        # --------------------------------------------------
        # 2. System instructions
        # --------------------------------------------------

        system_prompt = """
You are an autonomous browser automation agent.

Your job is to decide the NEXT browser action
required to complete the user's task.

You can choose ONLY one of these actions:

1. navigate
2. click
3. type
4. scroll
5. done

IMPORTANT:
Return ONLY a valid JSON object.

Do NOT return:
- markdown
- code fences
- <think> tags
- explanations outside JSON
- reasoning outside JSON

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

For completed tasks:
{
    "action": "done",
    "reason": "..."
}

Choose exactly ONE action.

The JSON must always contain:
- action
- reason

Do not invent actions outside the allowed list.
"""

        # --------------------------------------------------
        # 3. Current browser observation
        # --------------------------------------------------

        user_prompt = f"""
TASK:
{task}

CURRENT BROWSER STATE:

URL:
{observation.url}

TITLE:
{observation.title}

VISIBLE TEXT:
{observation.text[:8000]}

The screenshot shows the current visual browser state.

Use BOTH:
1. the screenshot
2. the visible browser text

Decide the single best NEXT action.

Return only the JSON object.
"""

        # --------------------------------------------------
        # 4. Ask Groq
        # --------------------------------------------------

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,

            # Force valid JSON output.
            # This prevents <think>...</think>
            # from appearing around the JSON.
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

        # --------------------------------------------------
        # 5. Extract LLM response
        # --------------------------------------------------

        content = response.choices[0].message.content

        if not content:
            raise ValueError(
                "Groq returned an empty response."
            )

        # Useful while debugging the agent.
        print("\n--- GROQ RESPONSE ---")
        print(content)

        # --------------------------------------------------
        # 6. Parse JSON
        # --------------------------------------------------

        try:
            data = json.loads(content)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Groq returned invalid JSON: {content}"
            ) from exc

        # --------------------------------------------------
        # 7. Validate action with Pydantic
        # --------------------------------------------------

        try:
            action = BrowserAction.model_validate(data)

        except Exception as exc:
            raise ValueError(
                f"Groq returned an invalid browser action: {data}"
            ) from exc

        return action