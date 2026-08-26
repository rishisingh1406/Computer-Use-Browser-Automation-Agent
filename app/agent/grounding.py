from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image


# ============================================================
# Data model
# ============================================================


@dataclass
class VisionTarget:
    found: bool
    x: float | None
    y: float | None
    reason: str = ""

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "VisionTarget":
        return cls(
            found=bool(data.get("found", False)),
            x=data.get("x"),
            y=data.get("y"),
            reason=str(data.get("reason", "")),
        )


# ============================================================
# Vision Grounder
# ============================================================


class VisionGrounder:
    """
    Vision-assisted browser element grounding.

    Pipeline:

        screenshot
            |
            v
        OpenRouter multimodal model
            |
            v
        normalized bbox [x1, y1, x2, y2]
            |
            v
        validate bbox
            |
            v
        convert normalized coordinates to pixels
            |
            v
        calculate center
            |
            v
        return VisionTarget

    The model is asked to return coordinates in a normalized
    0-1000 coordinate system.

    Python performs the final conversion to screenshot pixels.

    The implementation intentionally uses httpx directly rather
    than the OpenAI SDK so that OpenRouter-specific behavior is
    easier to inspect and debug.
    """

    NORMALIZED_SIZE = 1000

    OPENROUTER_URL = (
        "https://openrouter.ai/api/v1/chat/completions"
    )

    DEFAULT_MODEL = (
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    )

    # ========================================================
    # Initialization
    # ========================================================

    def __init__(
        self,
        model: str | None = None,
    ) -> None:

        api_key = os.getenv(
            "OPENROUTER_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY environment variable "
                "is not set."
            )

        self.api_key = api_key

        self.model = (
            model
            or os.getenv(
                "OPENROUTER_VISION_MODEL",
                self.DEFAULT_MODEL,
            )
        )

        print(
            f"OpenRouter vision model: {self.model}"
        )

    # ========================================================
    # Image loading
    # ========================================================

    @staticmethod
    def _load_image(
        screenshot_path: str,
    ) -> Image.Image:

        path = Path(
            screenshot_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Screenshot not found: {path}"
            )

        image = Image.open(path)

        if image.width <= 0 or image.height <= 0:
            raise ValueError(
                "Screenshot has invalid dimensions."
            )

        return image.convert("RGB")

    # ========================================================
    # Image encoding
    # ========================================================

    @staticmethod
    def _encode_png(
        image: Image.Image,
    ) -> str:

        buffer = BytesIO()

        image.save(
            buffer,
            format="PNG",
        )

        return base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

    # ========================================================
    # System prompt
    # ========================================================

    @staticmethod
    def _system_prompt(
        width: int,
        height: int,
    ) -> str:

        return f"""
You are a precise visual grounding system for browser automation.

Your ONLY job is to locate the exact visible UI element requested
by the user inside the supplied screenshot.

SCREENSHOT DIMENSIONS

width = {width} pixels
height = {height} pixels

COORDINATE SYSTEM

The screenshot uses:

origin = top-left

x increases from left to right

y increases from top to bottom

You MUST return normalized coordinates from 0 to 1000.

bbox format:

[x1, y1, x2, y2]

Conversion:

pixel_x = normalized_x / 1000 * {width}

pixel_y = normalized_y / 1000 * {height}

VISUAL GROUNDING RULES

1. Inspect the screenshot itself.

2. Locate the actual visible target.

3. Do not guess the location.

4. Do not infer the location from HTML.

5. Do not infer the location from DOM structure.

6. Do not infer the location from typical webpage layouts.

7. Do not infer the location from semantic expectations.

8. Do not choose a surrounding paragraph.

9. Do not choose a surrounding container.

10. Do not choose a surrounding section.

11. Do not choose another similar element.

12. If the target is text, locate the actual rendered text.

13. The bbox must tightly surround the visible target.

14. Keep the bbox as small as reasonably possible.

15. Inspect the entire screenshot before deciding.

16. x1 < x2.

17. y1 < y2.

18. All coordinates must be between 0 and 1000.

19. Do not return pixel coordinates.

20. Do not return percentages.

TEXT LINK RULE

If the target is:

"the Learn More link"

locate the actual visible characters:

"Learn More"

Do NOT return the paragraph containing the link.

Do NOT return the surrounding container.

Do NOT return an estimated location.

OUTPUT FORMAT

Return exactly one JSON object.

Visible target:

{{
    "found": true,
    "bbox_2d": [x1, y1, x2, y2],
    "reason": "short explanation"
}}

Target not visible:

{{
    "found": false,
    "bbox_2d": null,
    "reason": "target not visible"
}}

Do not output markdown.

Do not output code fences.

Do not output <think> blocks.

Do not output analysis.

Do not output multiple JSON objects.
"""

    # ========================================================
    # User prompt
    # ========================================================

    @staticmethod
    def _user_prompt(
        description: str,
    ) -> str:

        return f"""
Locate the EXACT visible browser UI element:

"{description}"

This is a visual grounding task.

Carefully inspect the supplied screenshot.

The target must be located from its actual visible
appearance in the screenshot.

If the target is a text link, locate the actual
rendered characters of the link.

For example, if the target is:

"the Learn More link"

locate the actual visible words:

"Learn More"

and return a tight bounding box around those
visible characters.

DO NOT:

- guess the location
- infer the location from HTML
- infer the location from DOM structure
- infer the location from page layout
- infer the location from semantic meaning
- choose a paragraph containing the target
- choose a surrounding container
- choose a surrounding section
- choose another similar element
- estimate the position

Inspect the entire screenshot.

Return normalized coordinates from 0 to 1000.

Return ONLY one JSON object:

{{
    "found": true,
    "bbox_2d": [x1, y1, x2, y2],
    "reason": "short explanation"
}}

If the target is not visible:

{{
    "found": false,
    "bbox_2d": null,
    "reason": "target not visible"
}}
"""

    # ========================================================
    # JSON extraction
    # ========================================================

    @staticmethod
    def _parse_json(
        content: str,
    ) -> dict[str, Any]:

        if not content or not content.strip():
            raise ValueError(
                "Vision response is empty."
            )

        original_content = content.strip()

        # ----------------------------------------------------
        # Attempt 1: direct JSON
        # ----------------------------------------------------

        try:
            data = json.loads(
                original_content
            )

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

        # ----------------------------------------------------
        # Remove thinking blocks
        # ----------------------------------------------------

        cleaned = re.sub(
            r"<think>.*?</think>",
            "",
            original_content,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        # ----------------------------------------------------
        # Remove markdown fences
        # ----------------------------------------------------

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
        ).strip()

        # ----------------------------------------------------
        # Attempt 2: cleaned JSON
        # ----------------------------------------------------

        if cleaned:

            try:
                data = json.loads(
                    cleaned
                )

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                pass

        # ----------------------------------------------------
        # Attempt 3: extract first JSON object
        # ----------------------------------------------------

        source = (
            cleaned
            or original_content
        )

        start = source.find("{")

        if start == -1:
            raise ValueError(
                "Vision response does not contain JSON.\n"
                f"Response: {original_content}"
            )

        depth = 0
        in_string = False
        escape = False

        for index in range(
            start,
            len(source),
        ):

            char = source[index]

            if char == "\\" and not escape:
                escape = True
                continue

            if char == '"' and not escape:
                in_string = not in_string

            escape = False

            if in_string:
                continue

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:

                    candidate = source[
                        start:index + 1
                    ]

                    try:
                        data = json.loads(
                            candidate
                        )

                        if isinstance(data, dict):
                            return data

                    except json.JSONDecodeError:
                        pass

                    break

        raise ValueError(
            "Invalid JSON response:\n"
            + original_content
        )

    # ========================================================
    # Validate bounding box
    # ========================================================

    @classmethod
    def _validate_bbox(
        cls,
        bbox: Any,
    ) -> tuple[
        float,
        float,
        float,
        float,
    ]:

        if not isinstance(
            bbox,
            (list, tuple),
        ):
            raise ValueError(
                "Vision model returned an invalid bbox_2d."
            )

        if len(bbox) != 4:
            raise ValueError(
                "bbox_2d must contain exactly four values."
            )

        try:

            x1 = float(bbox[0])
            y1 = float(bbox[1])
            x2 = float(bbox[2])
            y2 = float(bbox[3])

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                "bbox_2d contains non-numeric values."
            ) from exc

        values = (
            x1,
            y1,
            x2,
            y2,
        )

        if not all(
            0 <= value <= cls.NORMALIZED_SIZE
            for value in values
        ):
            raise ValueError(
                "bbox_2d coordinates must be between "
                "0 and 1000."
            )

        if x2 <= x1:
            raise ValueError(
                "bbox_2d has invalid horizontal bounds."
            )

        if y2 <= y1:
            raise ValueError(
                "bbox_2d has invalid vertical bounds."
            )

        return (
            x1,
            y1,
            x2,
            y2,
        )

    # ========================================================
    # Normalized bbox -> pixels
    # ========================================================

    @classmethod
    def _normalized_bbox_to_pixels(
        cls,
        image: Image.Image,
        bbox: tuple[
            float,
            float,
            float,
            float,
        ],
    ) -> tuple[
        float,
        float,
        float,
        float,
    ]:

        width = image.width
        height = image.height

        x1, y1, x2, y2 = bbox

        pixel_x1 = (
            x1
            / cls.NORMALIZED_SIZE
            * width
        )

        pixel_y1 = (
            y1
            / cls.NORMALIZED_SIZE
            * height
        )

        pixel_x2 = (
            x2
            / cls.NORMALIZED_SIZE
            * width
        )

        pixel_y2 = (
            y2
            / cls.NORMALIZED_SIZE
            * height
        )

        return (
            pixel_x1,
            pixel_y1,
            pixel_x2,
            pixel_y2,
        )

    # ========================================================
    # Calculate bbox center
    # ========================================================

    @staticmethod
    def _bbox_center(
        bbox: tuple[
            float,
            float,
            float,
            float,
        ],
    ) -> tuple[
        float,
        float,
    ]:

        x1, y1, x2, y2 = bbox

        center_x = (
            x1 + x2
        ) / 2

        center_y = (
            y1 + y2
        ) / 2

        return (
            center_x,
            center_y,
        )

    # ========================================================
    # Extract text from OpenRouter response
    # ========================================================

    @staticmethod
    def _extract_content(
        response_json: dict[str, Any],
    ) -> str:

        choices = response_json.get(
            "choices"
        )

        if not choices:
            raise ValueError(
                "OpenRouter returned no choices.\n"
                f"Response: {json.dumps(response_json, indent=2)}"
            )

        choice = choices[0]

        message = choice.get(
            "message"
        )

        if not message:
            raise ValueError(
                "OpenRouter returned no message.\n"
                f"Response: {json.dumps(response_json, indent=2)}"
            )

        content = message.get(
            "content"
        )

        # ----------------------------------------------------
        # Normal case
        # ----------------------------------------------------

        if isinstance(
            content,
            str,
        ) and content.strip():

            return content.strip()

        # ----------------------------------------------------
        # Some reasoning models may return structured
        # content blocks.
        # ----------------------------------------------------

        if isinstance(
            content,
            list,
        ):

            text_parts: list[str] = []

            for item in content:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                text = item.get(
                    "text"
                )

                if isinstance(
                    text,
                    str,
                ):
                    text_parts.append(
                        text
                    )

            combined = "\n".join(
                text_parts
            ).strip()

            if combined:
                return combined

        # ----------------------------------------------------
        # Some providers may put the final response
        # somewhere else.
        # ----------------------------------------------------

        for key in (
            "output_text",
            "text",
        ):

            value = response_json.get(
                key
            )

            if isinstance(
                value,
                str,
            ) and value.strip():

                return value.strip()

        # ----------------------------------------------------
        # Nothing usable
        # ----------------------------------------------------

        raise ValueError(
            "OpenRouter returned an empty response.\n\n"
            "Full response:\n"
            + json.dumps(
                response_json,
                indent=2,
                ensure_ascii=False,
            )
        )

    # ========================================================
    # Ask vision model
    # ========================================================

    async def _locate_bbox(
        self,
        image: Image.Image,
        description: str,
    ) -> dict[str, Any]:

        image_base64 = self._encode_png(
            image
        )

        width = image.width
        height = image.height

        system_prompt = self._system_prompt(
            width=width,
            height=height,
        )

        prompt = self._user_prompt(
            description=description,
        )

        payload = {
            "model": self.model,

            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/png;base64,"
                                    + image_base64
                                )
                            },
                        },
                    ],
                },
            ],

            "temperature": 0,

            "max_tokens": 256,

            # IMPORTANT:
            #
            # Nemotron 3 Nano Omni free does NOT support
            # response_format according to OpenRouter.
            #
            # Therefore we intentionally DO NOT send:
            #
            # "response_format": {
            #     "type": "json_object"
            # }
        }

        headers = {
            "Authorization": (
                f"Bearer {self.api_key}"
            ),

            "Content-Type": "application/json",

            "HTTP-Referer": (
                "http://localhost"
            ),

            "X-Title": (
                "Computer Use Browser Agent"
            ),
        }

        print(
            "\n--- OPENROUTER REQUEST ---"
        )

        print(
            "Model:",
            self.model,
        )

        # ====================================================
        # HTTP request
        # ====================================================

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:

            response = await client.post(
                self.OPENROUTER_URL,
                headers=headers,
                json=payload,
            )

        # ====================================================
        # HTTP validation
        # ====================================================

        print(
            "\nOPENROUTER STATUS:",
            response.status_code,
        )

        if response.status_code != 200:

            raise RuntimeError(
                "OpenRouter API request failed.\n"
                f"Status: {response.status_code}\n"
                f"Response:\n{response.text}"
            )

        # ====================================================
        # Parse response JSON
        # ====================================================

        try:

            response_json = response.json()

        except ValueError as exc:

            raise RuntimeError(
                "OpenRouter returned non-JSON HTTP response.\n"
                f"Response:\n{response.text}"
            ) from exc

        print(
            "\nOPENROUTER RAW RESPONSE:"
        )

        print(
            json.dumps(
                response_json,
                indent=2,
                ensure_ascii=False,
            )
        )

        # ====================================================
        # Extract model content
        # ====================================================

        content = self._extract_content(
            response_json
        )

        print(
            "\nRAW VISION RESPONSE:"
        )

        print(
            repr(content)
        )

        # ====================================================
        # Parse JSON ourselves
        # ====================================================

        return self._parse_json(
            content
        )

    # ========================================================
    # Public locate
    # ========================================================

    async def locate(
        self,
        screenshot_path: str,
        description: str,
    ) -> VisionTarget:

        if not description.strip():

            raise ValueError(
                "Element description cannot be empty."
            )

        # ----------------------------------------------------
        # Load screenshot
        # ----------------------------------------------------

        image = self._load_image(
            screenshot_path
        )

        print(
            "\n--- SCREENSHOT DIMENSIONS ---"
        )

        print(
            f"width={image.width}, "
            f"height={image.height}"
        )

        print(
            "\n--- VISION GROUNDING ---"
        )

        print(
            "Target:",
            description,
        )

        print(
            "Requested Model:",
            self.model,
        )

        # ----------------------------------------------------
        # Ask vision model
        # ----------------------------------------------------

        data = await self._locate_bbox(
            image=image,
            description=description,
        )

        # ----------------------------------------------------
        # Target not found
        # ----------------------------------------------------

        found = bool(
            data.get(
                "found",
                False,
            )
        )

        if not found:

            reason = str(
                data.get(
                    "reason",
                    "target not found",
                )
            )

            print(
                "\nVision target not found:",
                reason,
            )

            return VisionTarget(
                found=False,
                x=None,
                y=None,
                reason=reason,
            )

        # ----------------------------------------------------
        # Extract bbox
        # ----------------------------------------------------

        bbox_data = data.get(
            "bbox_2d"
        )

        bbox = self._validate_bbox(
            bbox_data
        )

        print(
            "\nNORMALIZED BBOX:"
        )

        print(
            f"x1={bbox[0]:.2f}"
        )

        print(
            f"y1={bbox[1]:.2f}"
        )

        print(
            f"x2={bbox[2]:.2f}"
        )

        print(
            f"y2={bbox[3]:.2f}"
        )

        # ----------------------------------------------------
        # Convert normalized bbox to pixels
        # ----------------------------------------------------

        pixel_bbox = (
            self._normalized_bbox_to_pixels(
                image=image,
                bbox=bbox,
            )
        )

        print(
            "\nPIXEL BBOX:"
        )

        print(
            f"x1={pixel_bbox[0]:.2f}"
        )

        print(
            f"y1={pixel_bbox[1]:.2f}"
        )

        print(
            f"x2={pixel_bbox[2]:.2f}"
        )

        print(
            f"y2={pixel_bbox[3]:.2f}"
        )

        # ----------------------------------------------------
        # Calculate center
        # ----------------------------------------------------

        center_x, center_y = (
            self._bbox_center(
                pixel_bbox
            )
        )

        print(
            "\nFINAL VISION CENTER:"
        )

        print(
            f"x={center_x:.2f}"
        )

        print(
            f"y={center_y:.2f}"
        )

        # ----------------------------------------------------
        # Reason
        # ----------------------------------------------------

        reason = str(
            data.get(
                "reason",
                "vision bounding-box grounding",
            )
        )

        return VisionTarget(
            found=True,
            x=center_x,
            y=center_y,
            reason=reason,
        )