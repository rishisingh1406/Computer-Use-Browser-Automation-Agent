from __future__ import annotations

from pathlib import Path

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

        await self.page.locator(selector).click()

        return {
            "action": "click",
            "selector": selector,
            "url": self.page.url,
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

        The screenshot metadata also records the browser viewport
        and devicePixelRatio so coordinate transformations can be
        diagnosed.
        """

        output_path = Path(path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # --------------------------------------------------------
        # Capture screenshot
        # --------------------------------------------------------

        await self.page.screenshot(
            path=str(output_path),
            full_page=full_page,
        )

        # --------------------------------------------------------
        # Browser viewport diagnostics
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
        Click a point using Playwright viewport coordinates.

        IMPORTANT:

        Playwright mouse coordinates are CSS viewport coordinates.

        VisionGrounder returns coordinates based on the screenshot
        pixel dimensions.

        Therefore, if screenshot pixels differ from CSS viewport
        dimensions because of devicePixelRatio, we scale the
        screenshot coordinates back into CSS coordinates.
        """

        # --------------------------------------------------------
        # Validate input types
        # --------------------------------------------------------

        try:
            x = float(x)
            y = float(y)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "x and y coordinates must be numeric."
            ) from exc

        # --------------------------------------------------------
        # Get browser viewport information
        # --------------------------------------------------------

        viewport = await self.page.evaluate(
            """
            () => ({
                width: window.innerWidth,
                height: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio
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
        # Get actual screenshot dimensions
        # --------------------------------------------------------

        screenshot_width = viewport_width
        screenshot_height = viewport_height

        # Playwright screenshots are normally emitted at the
        # device scale factor, so inspect the current page's
        # screenshot dimensions indirectly using a temporary
        # screenshot buffer.
        screenshot_bytes = await self.page.screenshot(
            full_page=False,
        )

        # Import locally to keep the normal tool surface small.
        from io import BytesIO

        from PIL import Image

        screenshot_image = Image.open(
            BytesIO(screenshot_bytes)
        )

        screenshot_width = float(
            screenshot_image.width
        )

        screenshot_height = float(
            screenshot_image.height
        )

        # --------------------------------------------------------
        # Convert screenshot pixels -> CSS viewport coordinates
        # --------------------------------------------------------

        if screenshot_width <= 0:
            raise ValueError(
                "Screenshot width is invalid."
            )

        if screenshot_height <= 0:
            raise ValueError(
                "Screenshot height is invalid."
            )

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

        if css_x < 0 or css_x >= viewport_width:
            raise ValueError(
                f"x coordinate {x} from screenshot "
                f"converts to CSS x={css_x:.2f}, "
                f"outside viewport width "
                f"{viewport_width:.0f}"
            )

        if css_y < 0 or css_y >= viewport_height:
            raise ValueError(
                f"y coordinate {y} from screenshot "
                f"converts to CSS y={css_y:.2f}, "
                f"outside viewport height "
                f"{viewport_height:.0f}"
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

        # --------------------------------------------------------
        # Perform click
        # --------------------------------------------------------

        await self.page.mouse.click(
            css_x,
            css_y,
        )

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