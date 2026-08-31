from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.async_api import Page


class BrowserTools:
    """
    Agent-facing browser tools.

    These methods provide a controlled interface between
    the agent and Playwright.

    Design principles:
        - Playwright remains the execution layer.
        - LLM never receives direct browser access.
        - DOM selectors are preferred for deterministic actions.
        - Coordinate actions are used for visual grounding.
        - Security-sensitive elements can be inspected before execution.
    """

    def __init__(self, page: Page):
        self.page = page

    # ============================================================
    # Navigation
    # ============================================================

    async def navigate(
        self,
        url: str,
    ) -> dict:
        """Navigate to a URL."""

        response = await self.page.goto(
            url,
            wait_until="domcontentloaded",
        )

        return {
            "action": "navigate",
            "url": self.page.url,
            "title": await self.page.title(),
            "status": response.status if response else None,
        }

    # ============================================================
    # Selector click
    # ============================================================

    async def click(
        self,
        selector: str,
    ) -> dict:
        """
        Click an element using a CSS selector.

        This method intentionally performs only the browser action.
        Security-sensitive actions should be inspected by the
        security/guardrail layer before reaching this method.
        """

        locator = self.page.locator(
            selector
        ).first

        if not await locator.count():
            raise ValueError(
                f"Element not found: {selector}"
            )

        previous_url = self.page.url

        await locator.click()

        try:
            await self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=5000,
            )
        except Exception:
            # The click may not trigger navigation.
            pass

        await self.page.wait_for_timeout(250)

        final_url = self.page.url

        return {
            "action": "click",
            "selector": selector,
            "previous_url": previous_url,
            "url": final_url,
            "navigated": final_url != previous_url,
        }

    # ============================================================
    # Type text
    # ============================================================

    async def type_text(
        self,
        selector: str,
        text: str,
    ) -> dict:
        """Enter text into an input element."""

        locator = self.page.locator(
            selector
        ).first

        if not await locator.count():
            raise ValueError(
                f"Element not found: {selector}"
            )

        await locator.fill(text)

        return {
            "action": "type",
            "selector": selector,
            "text_length": len(text),
        }

    # ============================================================
    # Screenshot
    # ============================================================

    async def screenshot(
        self,
        path: str = "screenshots/page.png",
        full_page: bool = False,
    ) -> dict:
        """
        Capture the browser viewport.

        full_page=False is important for visual grounding because
        VisionGrounder coordinates are relative to the screenshot.
        """

        output_path = Path(path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        await self.page.screenshot(
            path=str(output_path),
            full_page=full_page,
        )

        viewport = await self.page.evaluate(
            """
            () => ({
                width: window.innerWidth,
                height: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio,
                scrollX: window.scrollX,
                scrollY: window.scrollY
            })
            """
        )

        return {
            "action": "screenshot",
            "path": str(output_path),
            "full_page": full_page,
            "viewport": viewport,
        }

    # ============================================================
    # Read page text
    # ============================================================

    async def read_text(self) -> dict:
        """Read visible text from the current page."""

        text = await self.page.locator(
            "body"
        ).inner_text()

        return {
            "action": "read_text",
            "text": text,
        }

    # ============================================================
    # Coordinate click
    # ============================================================

    async def click_coordinates(
        self,
        x: float,
        y: float,
    ) -> dict:
        """
        Click a point using screenshot coordinates.

        VisionGrounder returns coordinates relative to the screenshot.

        Playwright mouse.click() expects CSS viewport coordinates.

        Therefore:

            screenshot pixels
                    ↓
            CSS viewport coordinates
                    ↓
            Playwright mouse.click()

        The method also:

            1. validates coordinates
            2. inspects the DOM element under the point
            3. detects whether the target is likely a link
            4. performs exactly one click
            5. waits for browser events to settle
            6. returns structured diagnostics
        """

        # --------------------------------------------------------
        # Validate input
        # --------------------------------------------------------

        try:
            x = float(x)
            y = float(y)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "x and y coordinates must be numeric."
            ) from exc

        if x < 0 or y < 0:
            raise ValueError(
                "x and y coordinates must be non-negative."
            )

        # --------------------------------------------------------
        # Browser viewport
        # --------------------------------------------------------

        viewport = await self.page.evaluate(
            """
            () => ({
                width: window.innerWidth,
                height: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio,
                scrollX: window.scrollX,
                scrollY: window.scrollY
            })
            """
        )

        viewport_width = float(
            viewport["width"]
        )

        viewport_height = float(
            viewport["height"]
        )

        device_pixel_ratio = float(
            viewport["devicePixelRatio"]
        )

        if viewport_width <= 0 or viewport_height <= 0:
            raise ValueError(
                "Browser viewport dimensions are invalid."
            )

        # --------------------------------------------------------
        # Determine actual screenshot dimensions
        # --------------------------------------------------------

        screenshot_bytes = await self.page.screenshot(
            full_page=False,
        )

        screenshot_image = Image.open(
            BytesIO(screenshot_bytes)
        )

        screenshot_width = float(
            screenshot_image.width
        )

        screenshot_height = float(
            screenshot_image.height
        )

        if screenshot_width <= 0:
            raise ValueError(
                "Screenshot width is invalid."
            )

        if screenshot_height <= 0:
            raise ValueError(
                "Screenshot height is invalid."
            )

        # --------------------------------------------------------
        # Screenshot pixels -> CSS viewport coordinates
        # --------------------------------------------------------

        css_x = (
            x
            * viewport_width
            / screenshot_width
        )

        css_y = (
            y
            * viewport_height
            / screenshot_height
        )

        # --------------------------------------------------------
        # Validate converted coordinates
        # --------------------------------------------------------

        if not (
            0 <= css_x < viewport_width
        ):
            raise ValueError(
                f"x coordinate {x} converts to "
                f"CSS x={css_x:.2f}, outside viewport."
            )

        if not (
            0 <= css_y < viewport_height
        ):
            raise ValueError(
                f"y coordinate {y} converts to "
                f"CSS y={css_y:.2f}, outside viewport."
            )

        # --------------------------------------------------------
        # Inspect element under coordinate
        # --------------------------------------------------------

        element_info = await self.page.evaluate(
            """
            ({x, y}) => {

                const element =
                    document.elementFromPoint(x, y);

                if (!element) {
                    return null;
                }

                const anchor =
                    element.closest("a");

                const target =
                    anchor || element;

                const form =
                    target.closest("form");

                return {
                    tag: (
                        target.tagName || ""
                    ).toLowerCase(),

                    text: (
                        target.innerText ||
                        target.textContent ||
                        ""
                    ).trim(),

                    href:
                        target.href ||
                        null,

                    id:
                        target.id ||
                        null,

                    className:
                        typeof target.className === "string"
                            ? target.className
                            : null,

                    role:
                        target.getAttribute("role") ||
                        null,

                    aria_label:
                        target.getAttribute("aria-label") ||
                        null,

                    type:
                        target.getAttribute("type") ||
                        null,

                    name:
                        target.getAttribute("name") ||
                        null,

                    form_action:
                        form?.action ||
                        null
                };
            }
            """,
            {
                "x": css_x,
                "y": css_y,
            },
        )

        # --------------------------------------------------------
        # Current URL
        # --------------------------------------------------------

        previous_url = self.page.url

        # --------------------------------------------------------
        # Determine navigation expectation
        # --------------------------------------------------------

        navigation_expected = bool(
            element_info
            and element_info.get("href")
        )

        navigation_started = False

        # --------------------------------------------------------
        # Click exactly once
        # --------------------------------------------------------

        if navigation_expected:
            try:
                async with self.page.expect_navigation(
                    wait_until="domcontentloaded",
                    timeout=5000,
                ):
                    await self.page.mouse.click(
                        css_x,
                        css_y,
                    )

                navigation_started = True

            except Exception:
                # The click itself may still have succeeded.
                # Never click a second time.
                navigation_started = False

        else:
            await self.page.mouse.click(
                css_x,
                css_y,
            )

        # --------------------------------------------------------
        # Allow browser events/navigation to settle
        # --------------------------------------------------------

        await self.page.wait_for_timeout(
            500
        )

        # --------------------------------------------------------
        # Final URL
        # --------------------------------------------------------

        final_url = self.page.url

        navigated = (
            final_url != previous_url
        )

        # --------------------------------------------------------
        # Return structured result
        # --------------------------------------------------------

        return {
            "action": "click_coordinates",
            "x": x,
            "y": y,
            "css_x": css_x,
            "css_y": css_y,
            "screenshot_width": screenshot_width,
            "screenshot_height": screenshot_height,
            "viewport_width": viewport_width,
            "viewport_height": viewport_height,
            "device_pixel_ratio": device_pixel_ratio,
            "element": element_info,
            "previous_url": previous_url,
            "url": final_url,
            "navigation_expected": navigation_expected,
            "navigation_started": navigation_started,
            "navigated": navigated,
        }

    # ============================================================
    # Scroll
    # ============================================================

    async def scroll(
        self,
        direction: str = "down",
    ) -> dict:
        """Scroll the page up or down."""

        direction = direction.lower().strip()

        if direction == "down":
            await self.page.mouse.wheel(
                0,
                800,
            )

        elif direction == "up":
            await self.page.mouse.wheel(
                0,
                -800,
            )

        else:
            raise ValueError(
                "direction must be 'up' or 'down'"
            )

        await self.page.wait_for_timeout(
            250
        )

        scroll_position = await self.page.evaluate(
            """
            () => ({
                scrollX: window.scrollX,
                scrollY: window.scrollY,
                documentHeight:
                    document.documentElement.scrollHeight,
                viewportHeight:
                    window.innerHeight
            })
            """
        )

        return {
            "action": "scroll",
            "direction": direction,
            "scroll": scroll_position,
        }

    # ============================================================
    # Inspect selector
    # ============================================================

    async def inspect_selector(
        self,
        selector: str,
    ) -> dict:
        """
        Inspect a DOM element before executing an action.
        """

        locator = self.page.locator(
            selector
        ).first

        if not await locator.count():
            raise ValueError(
                f"Element not found: {selector}"
            )

        return await locator.evaluate(
            """
            (element, selector) => {

                const tag = (
                    element.tagName || ""
                ).toLowerCase();

                const type = (
                    element.getAttribute("type") || ""
                ).toLowerCase();

                const text = (
                    element.innerText ||
                    element.textContent ||
                    ""
                ).trim();

                const ariaLabel = (
                    element.getAttribute("aria-label") ||
                    ""
                ).trim();

                const name = (
                    element.getAttribute("name") ||
                    ""
                ).trim();

                const value = (
                    element.getAttribute("value") ||
                    ""
                ).trim();

                const anchor =
                    element.closest("a");

                const href =
                    anchor?.href ||
                    element.href ||
                    null;

                const form =
                    element.closest("form");

                const formAction =
                    form?.action ||
                    null;

                const dangerousWords = [
                    "submit",
                    "buy",
                    "purchase",
                    "place order",
                    "confirm",
                    "checkout",
                    "pay",
                    "send",
                    "book",
                    "reserve",
                    "delete",
                    "remove",
                    "cancel",
                    "transfer"
                ];

                const combinedText = [
                    text,
                    ariaLabel,
                    name,
                    value
                ]
                .join(" ")
                .toLowerCase();

                const isSubmitControl =
                    (
                        tag === "button" &&
                        (
                            type === "submit" ||
                            type === "button"
                        )
                    )
                    ||
                    (
                        tag === "input" &&
                        (
                            type === "submit" ||
                            type === "button"
                        )
                    );

                const hasDangerousText =
                    dangerousWords.some(
                        word =>
                            combinedText.includes(word)
                    );

                const submitType =
                    isSubmitControl ||
                    hasDangerousText;

                return {
                    selector,
                    tag,
                    type,
                    text,
                    aria_label: ariaLabel,
                    name,
                    value,
                    href,
                    form_action: formAction,
                    submit_type: submitType,
                    description: (
                        text ||
                        ariaLabel ||
                        name ||
                        value ||
                        selector
                    )
                };
            }
            """,
            selector,
        )
