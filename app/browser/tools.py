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
        """Click an element using a CSS selector."""

        locator = self.page.locator(selector)

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

        await self.page.locator(selector).fill(text)

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

        For visual grounding, full_page=False is important because
        VisionGrounder returns coordinates relative to the screenshot.
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

        VisionGrounder returns coordinates relative to the
        screenshot.

        Playwright mouse.click() expects CSS viewport
        coordinates.

        Therefore:

            screenshot coordinates
                    ↓
            CSS viewport coordinates
                    ↓
            Playwright mouse click

        The method also inspects the DOM element under the
        coordinate and waits for navigation when appropriate.
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
        # Validate coordinates
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

                return {
                    tag: target.tagName,

                    text: (
                        target.innerText ||
                        target.textContent ||
                        ""
                    ).trim(),

                    href: target.href || null,

                    id: target.id || null,

                    className:
                        typeof target.className === "string"
                            ? target.className
                            : null
                };
            }
            """,
            {
                "x": css_x,
                "y": css_y,
            },
        )

        # --------------------------------------------------------
        # Diagnostics
        # --------------------------------------------------------

        print(
            "\n--- COORDINATE CLICK ---"
        )

        print(
            f"Input screenshot coordinates: "
            f"({x:.2f}, {y:.2f})"
        )

        print(
            f"Screenshot dimensions: "
            f"{screenshot_width:.0f}x"
            f"{screenshot_height:.0f}"
        )

        print(
            f"Viewport dimensions: "
            f"{viewport_width:.0f}x"
            f"{viewport_height:.0f}"
        )

        print(
            f"Device pixel ratio: "
            f"{device_pixel_ratio:.2f}"
        )

        print(
            f"Converted CSS coordinates: "
            f"({css_x:.2f}, {css_y:.2f})"
        )

        print(
            "\nELEMENT UNDER COORDINATE:"
        )

        print(
            element_info
        )

        # --------------------------------------------------------
        # Current URL
        # --------------------------------------------------------

        previous_url = self.page.url

        # --------------------------------------------------------
        # Click
        # --------------------------------------------------------

        print(
            "\nCLICKING..."
        )

        navigation_expected = bool(
            element_info
            and element_info.get("href")
        )

        navigation_started = False

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

            except Exception as exc:

                print(
                    "\nNavigation event was not "
                    "observed:"
                )

                print(
                    exc
                )

                # The mouse click itself may still have
                # succeeded. Do not click a second time.

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
        # Diagnostics
        # --------------------------------------------------------

        print(
            "\nCLICK RESULT:"
        )

        print(
            f"Previous URL: {previous_url}"
        )

        print(
            f"Final URL:    {final_url}"
        )

        print(
            f"Navigation expected: "
            f"{navigation_expected}"
        )

        print(
            f"Navigation event detected: "
            f"{navigation_started}"
        )

        print(
            f"URL changed: "
            f"{navigated}"
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

        return {
            "action": "scroll",
            "direction": direction,
        }