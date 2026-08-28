import asyncio
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
        Decide HOW to perform the CURRENT browser subtask.

    The high-level planner has already decided WHAT
    needs to happen.

    This class decides the next concrete browser action.
    """

    DEFAULT_MODEL = "qwen/qwen3.6-27b"

    # Maximum number of retries after the first request.
    MAX_RETRIES = 2

    # Delay between browser LLM requests.
    #
    # This is NOT a fix for daily token limits.
    # It simply prevents sending requests too aggressively.
    REQUEST_DELAY = 1.0

    # Initial retry delay.
    DEFAULT_RETRY_DELAY = 1.0

    # Maximum visible text sent to the model.
    MAX_VISIBLE_TEXT = 8000

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
            or os.getenv("GROQ_BROWSER_MODEL")
            or self.DEFAULT_MODEL
        )

        print()
        print("GROQ BROWSER LLM")
        print(f"Model: {self.model}")

    # ==========================================================
    # IMAGE ENCODING
    # ==========================================================

    @staticmethod
    def _encode_image(
        image_path: str,
    ) -> str:
        """
        Encode browser screenshot as base64.
        """

        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Screenshot not found: {image_path}"
            )

        image_bytes = path.read_bytes()

        if not image_bytes:
            raise ValueError(
                f"Screenshot is empty: {image_path}"
            )

        return base64.b64encode(
            image_bytes
        ).decode("utf-8")

    # ==========================================================
    # SYSTEM PROMPT
    # ==========================================================

    @staticmethod
    def _system_prompt() -> str:
        """
        Small, strict prompt.

        Keep this prompt compact because it is sent
        on every browser step.
        """

        return """
You are a low-level browser automation agent.

A high-level planner has already decided WHAT needs to happen.

Your job is to decide HOW to perform ONLY the CURRENT SUBTASK.

Return exactly ONE JSON object.

Allowed actions:
- navigate
- click
- type
- scroll
- done

Required JSON fields:

{
  "action": "navigate|click|type|scroll|done",
  "url": null,
  "selector": null,
  "text": null,
  "direction": null,
  "reason": "short explanation"
}

Rules:

1. Always return ALL six fields.
2. Never add extra fields.
3. Never return markdown.
4. Never return code fences.
5. Never return explanations outside JSON.
6. Complete ONLY the current subtask.
7. Do not perform the next planner step.
8. Use the current URL, title, visible text and screenshot.
9. Never invent browser state.
10. Return done ONLY when the current subtask is actually complete.

Action requirements:

navigate:
- url = required
- selector = null
- text = null
- direction = null

click:
- url = null
- selector = required
- text = null
- direction = null

type:
- url = null
- selector = required
- text = required
- direction = null

scroll:
- url = null
- selector = null
- text = null
- direction = "up" or "down"

done:
- url = null
- selector = null
- text = null
- direction = null

For click and type, use a CSS selector for a currently visible element.

For scroll, use it only when the requested information is not currently visible.

Return ONLY the JSON object.
""".strip()

    # ==========================================================
    # USER PROMPT
    # ==========================================================

    @staticmethod
    def _build_user_prompt(
        task: str,
        observation: BrowserObservation,
    ) -> str:
        """
        Build a compact browser-state prompt.

        Keep this small because it is sent repeatedly.
        """

        visible_text = observation.text[
            : GroqBrowserLLM.MAX_VISIBLE_TEXT
        ]

        return f"""
CURRENT SUBTASK:

{task}

CURRENT BROWSER STATE:

URL:
{observation.url}

TITLE:
{observation.title}

VISIBLE TEXT:
{visible_text}

Determine the SINGLE best next browser action.

Complete ONLY the current subtask.

Return ONLY JSON.

The JSON must contain exactly these six fields:

action
url
selector
text
direction
reason

If a field is not relevant to the selected action,
set it to null.
""".strip()

    # ==========================================================
    # ERROR CLASSIFICATION
    # ==========================================================

    @staticmethod
    def _error_message(
        exc: Exception,
    ) -> str:
        """
        Return a normalized lowercase error message.
        """

        return str(exc).lower()

    # ==========================================================
    # RATE LIMIT DETECTION
    # ==========================================================

    @staticmethod
    def _is_rate_limit_error(
        exc: Exception,
    ) -> bool:
        """
        Detect Groq rate-limit errors.

        429 / TPM / RPM / TPD errors are different from
        JSON validation errors.

        TPM/RPM can recover after waiting.

        TPD usually requires waiting for the daily limit reset.
        """

        message = GroqBrowserLLM._error_message(exc)

        return (
            "429" in message
            or "rate limit" in message
            or "rate_limit_exceeded" in message
            or "tokens per minute" in message
            or "tokens per day" in message
            or "requests per minute" in message
            or "requests per day" in message
            or "tpm" in message
            or "tpd" in message
            or "rpm" in message
            or "rpd" in message
        )

    # ==========================================================
    # JSON VALIDATION ERROR DETECTION
    # ==========================================================

    @staticmethod
    def _is_json_validation_error(
        exc: Exception,
    ) -> bool:
        """
        Detect Groq 400 JSON validation failures.

        Example:

        Failed to validate JSON.
        Please adjust your prompt.
        """

        message = GroqBrowserLLM._error_message(exc)

        return (
            "json_validate_failed" in message
            or "failed to validate json" in message
            or "generated json" in message
            or "json validation" in message
            or "invalid_request_error" in message
        )

    # ==========================================================
    # TRANSIENT ERROR DETECTION
    # ==========================================================

    @staticmethod
    def _is_transient_error(
        exc: Exception,
    ) -> bool:
        """
        Detect errors that may recover after a short delay.
        """

        message = GroqBrowserLLM._error_message(exc)

        return (
            "500" in message
            or "502" in message
            or "503" in message
            or "504" in message
            or "timeout" in message
            or "timed out" in message
            or "connection" in message
            or "temporarily unavailable" in message
            or "service unavailable" in message
        )

    # ==========================================================
    # GROQ REQUEST
    # ==========================================================

    async def _request(
        self,
        messages: list[dict],
    ):
        """
        Send request to Groq with controlled retry handling.

        Important:

        - Rate limits are handled separately.
        - JSON validation failures can be retried.
        - Server/network failures can be retried.
        - Daily token limits should not be blindly retried.
        """

        for attempt in range(
            self.MAX_RETRIES + 1
        ):
            try:

                # --------------------------------------------------
                # Small delay before every request after the first.
                #
                # This reduces burst pressure on RPM/TPM limits.
                # --------------------------------------------------

                if attempt > 0:
                    delay = (
                        self.DEFAULT_RETRY_DELAY
                        * attempt
                    )

                    print()
                    print(
                        "GROQ BROWSER RETRY"
                    )
                    print(
                        f"Attempt: {attempt + 1}/"
                        f"{self.MAX_RETRIES + 1}"
                    )
                    print(
                        f"Waiting {delay:.2f} seconds..."
                    )

                    await asyncio.sleep(
                        delay
                    )

                # --------------------------------------------------
                # Request
                # --------------------------------------------------

                response = (
                    self.client
                    .chat
                    .completions
                    .create(
                        model=self.model,

                        temperature=0,

                        # Qwen 3.6 supports reasoning_effort="none".
                        #
                        # This is appropriate here because this model
                        # only needs to choose one browser action.
                        reasoning_effort="none",

                        response_format={
                            "type": "json_object"
                        },

                        messages=messages,
                    )
                )

                # --------------------------------------------------
                # Small cooldown after successful request.
                #
                # This helps avoid hammering the API when the
                # BrowserAgent immediately asks for another action.
                # --------------------------------------------------

                await asyncio.sleep(
                    self.REQUEST_DELAY
                )

                return response

            except Exception as exc:

                # ==================================================
                # RATE LIMIT
                # ==================================================

                if self._is_rate_limit_error(
                    exc
                ):

                    message = self._error_message(
                        exc
                    )

                    # Daily token limits are not fixed by
                    # sleeping for one or two seconds.
                    if (
                        "tokens per day" in message
                        or "tpd" in message
                    ):
                        raise RuntimeError(
                            f"Groq daily token limit reached "
                            f"for model '{self.model}'.\n\n"
                            "Waiting a few seconds will not fix "
                            "a daily token limit.\n\n"
                            f"Original error: {exc}"
                        ) from exc

                    # TPM/RPM limits may recover.
                    if attempt < self.MAX_RETRIES:

                        retry_delay = max(
                            self.DEFAULT_RETRY_DELAY
                            * (attempt + 1),
                            2.0,
                        )

                        print()
                        print(
                            "GROQ RATE LIMIT"
                        )
                        print(
                            f"Retrying in "
                            f"{retry_delay:.2f} seconds..."
                        )

                        await asyncio.sleep(
                            retry_delay
                        )

                        continue

                    raise RuntimeError(
                        f"Groq rate limit reached for "
                        f"model '{self.model}' "
                        f"after {self.MAX_RETRIES + 1} attempts.\n\n"
                        f"Original error: {exc}"
                    ) from exc

                # ==================================================
                # JSON VALIDATION ERROR
                # ==================================================

                if self._is_json_validation_error(
                    exc
                ):

                    if attempt < self.MAX_RETRIES:

                        retry_delay = (
                            self.DEFAULT_RETRY_DELAY
                            * (attempt + 1)
                        )

                        print()
                        print(
                            "GROQ JSON VALIDATION RETRY"
                        )
                        print(
                            f"Attempt: {attempt + 1}/"
                            f"{self.MAX_RETRIES + 1}"
                        )
                        print(
                            f"Retrying in "
                            f"{retry_delay:.2f} seconds..."
                        )

                        await asyncio.sleep(
                            retry_delay
                        )

                        continue

                    raise RuntimeError(
                        "Groq repeatedly failed to generate "
                        "valid JSON for the browser action.\n\n"
                        "This is a model/output-format problem, "
                        "not a browser execution problem.\n\n"
                        f"Original error: {exc}"
                    ) from exc

                # ==================================================
                # TRANSIENT SERVER / NETWORK ERROR
                # ==================================================

                if self._is_transient_error(
                    exc
                ):

                    if attempt < self.MAX_RETRIES:

                        retry_delay = (
                            self.DEFAULT_RETRY_DELAY
                            * (attempt + 1)
                        )

                        print()
                        print(
                            "GROQ TRANSIENT ERROR"
                        )
                        print(
                            f"Retrying in "
                            f"{retry_delay:.2f} seconds..."
                        )

                        await asyncio.sleep(
                            retry_delay
                        )

                        continue

                # ==================================================
                # FINAL FAILURE
                # ==================================================

                if attempt >= self.MAX_RETRIES:

                    raise RuntimeError(
                        "Browser LLM request failed after "
                        f"{self.MAX_RETRIES + 1} attempts: "
                        f"{exc}"
                    ) from exc

                # Generic retry.
                retry_delay = (
                    self.DEFAULT_RETRY_DELAY
                    * (attempt + 1)
                )

                print()
                print(
                    "GROQ BROWSER RETRY"
                )
                print(
                    f"Retrying in "
                    f"{retry_delay:.2f} seconds..."
                )

                await asyncio.sleep(
                    retry_delay
                )

        raise RuntimeError(
            "Groq request failed unexpectedly."
        )

    # ==========================================================
    # LOW-LEVEL BROWSER DECISION
    # ==========================================================

    async def decide(
        self,
        task: str,
        observation: BrowserObservation,
    ) -> BrowserAction:
        """
        Decide the single next browser action.
        """

        # ------------------------------------------------------
        # Validate task
        # ------------------------------------------------------

        task = task.strip()

        if not task:
            raise ValueError(
                "Browser task cannot be empty."
            )

        # ------------------------------------------------------
        # Encode screenshot
        # ------------------------------------------------------

        image_data = self._encode_image(
            observation.screenshot_path
        )

        # ------------------------------------------------------
        # Build prompts
        # ------------------------------------------------------

        system_prompt = (
            self._system_prompt()
        )

        user_prompt = (
            self._build_user_prompt(
                task=task,
                observation=observation,
            )
        )

        # ------------------------------------------------------
        # Groq request
        # ------------------------------------------------------

        response = await self._request(
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
            ]
        )

        # ------------------------------------------------------
        # Extract response
        # ------------------------------------------------------

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:
            raise ValueError(
                "Groq returned an empty browser response."
            )

        print()
        print(
            "--- GROQ BROWSER RESPONSE ---"
        )
        print(content)

        # ------------------------------------------------------
        # Parse JSON
        # ------------------------------------------------------

        try:

            data = json.loads(
                content
            )

        except json.JSONDecodeError as exc:

            raise ValueError(
                "Groq returned invalid browser JSON: "
                f"{content}"
            ) from exc

        # ------------------------------------------------------
        # Validate JSON object
        # ------------------------------------------------------

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                "Groq browser response must be a JSON object. "
                f"Received: {type(data).__name__}"
            )

        # ------------------------------------------------------
        # Required fields
        # ------------------------------------------------------

        required_fields = {
            "action",
            "url",
            "selector",
            "text",
            "direction",
            "reason",
        }

        missing_fields = (
            required_fields
            - data.keys()
        )

        if missing_fields:

            raise ValueError(
                "Groq browser response is missing "
                f"required fields: "
                f"{sorted(missing_fields)}. "
                f"Response: {data}"
            )

        # ------------------------------------------------------
        # Reject unexpected fields
        # ------------------------------------------------------

        extra_fields = (
            set(data.keys())
            - required_fields
        )

        if extra_fields:

            raise ValueError(
                "Groq browser response contains "
                f"unexpected fields: "
                f"{sorted(extra_fields)}. "
                f"Response: {data}"
            )

        # ------------------------------------------------------
        # Validate Pydantic model
        # ------------------------------------------------------

        try:

            action = (
                BrowserAction
                .model_validate(data)
            )

        except Exception as exc:

            raise ValueError(
                "Groq returned an invalid "
                f"browser action: {data}"
            ) from exc

        # ------------------------------------------------------
        # Semantic validation
        # ------------------------------------------------------

        self._validate_action(
            action
        )

        return action

    # ==========================================================
    # ACTION VALIDATION
    # ==========================================================

    @staticmethod
    def _validate_action(
        action: BrowserAction,
    ) -> None:

        # ------------------------------------------------------
        # Reason
        # ------------------------------------------------------

        if not action.reason.strip():

            raise ValueError(
                "Browser action reason cannot be empty."
            )

        # ------------------------------------------------------
        # Navigate
        # ------------------------------------------------------

        if action.action == "navigate":

            if not action.url:
                raise ValueError(
                    "navigate action requires url."
                )

            if action.selector is not None:
                raise ValueError(
                    "navigate action must not contain selector."
                )

            if action.text is not None:
                raise ValueError(
                    "navigate action must not contain text."
                )

            if action.direction is not None:
                raise ValueError(
                    "navigate action must not contain direction."
                )

        # ------------------------------------------------------
        # Click
        # ------------------------------------------------------

        elif action.action == "click":

            if not action.selector:
                raise ValueError(
                    "click action requires selector."
                )

            if action.url is not None:
                raise ValueError(
                    "click action must not contain url."
                )

            if action.text is not None:
                raise ValueError(
                    "click action must not contain text."
                )

            if action.direction is not None:
                raise ValueError(
                    "click action must not contain direction."
                )

        # ------------------------------------------------------
        # Type
        # ------------------------------------------------------

        elif action.action == "type":

            if not action.selector:
                raise ValueError(
                    "type action requires selector."
                )

            if action.text is None:
                raise ValueError(
                    "type action requires text."
                )

            if action.url is not None:
                raise ValueError(
                    "type action must not contain url."
                )

            if action.direction is not None:
                raise ValueError(
                    "type action must not contain direction."
                )

        # ------------------------------------------------------
        # Scroll
        # ------------------------------------------------------

        elif action.action == "scroll":

            if action.direction not in {
                "up",
                "down",
            }:

                raise ValueError(
                    "scroll action requires direction "
                    "'up' or 'down'."
                )

            if action.url is not None:
                raise ValueError(
                    "scroll action must not contain url."
                )

            if action.selector is not None:
                raise ValueError(
                    "scroll action must not contain selector."
                )

            if action.text is not None:
                raise ValueError(
                    "scroll action must not contain text."
                )

        # ------------------------------------------------------
        # Done
        # ------------------------------------------------------

        elif action.action == "done":

            if action.url is not None:
                raise ValueError(
                    "done action must not contain url."
                )

            if action.selector is not None:
                raise ValueError(
                    "done action must not contain selector."
                )

            if action.text is not None:
                raise ValueError(
                    "done action must not contain text."
                )

            if action.direction is not None:
                raise ValueError(
                    "done action must not contain direction."
                )

