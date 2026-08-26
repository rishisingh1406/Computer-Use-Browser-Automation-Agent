import math

import pytest

from app.agent.grounding import VisionGrounder
from app.browser.manager import BrowserManager
from app.browser.tools import BrowserTools


@pytest.mark.asyncio
async def test_visual_click():
    manager = BrowserManager(headless=True)

    page = await manager.start()
    tools = BrowserTools(page)

    try:
        # --------------------------------
        # Navigate
        # --------------------------------

        await tools.navigate(
            "https://example.com"
        )

        # --------------------------------
        # Browser viewport diagnostics
        # --------------------------------

        viewport = await page.evaluate(
            """
            () => ({
                width: window.innerWidth,
                height: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio
            })
            """
        )

        print("\nVIEWPORT:")
        print(viewport)

        # --------------------------------
        # Get actual DOM position
        # --------------------------------

        link = page.locator("a")

        link_box = await link.bounding_box()

        print("\nACTUAL LINK BOX:")
        print(link_box)

        assert link_box is not None

        # --------------------------------
        # Calculate DOM center
        # --------------------------------

        dom_center_x = (
            link_box["x"]
            + link_box["width"] / 2
        )

        dom_center_y = (
            link_box["y"]
            + link_box["height"] / 2
        )

        print("\nACTUAL DOM CENTER:")
        print(
            f"x={dom_center_x:.2f}, "
            f"y={dom_center_y:.2f}"
        )

        # --------------------------------
        # Take viewport screenshot
        # --------------------------------

        screenshot_path = (
            "screenshots/grounding-test.png"
        )

        await tools.screenshot(
            screenshot_path,
            full_page=False,
        )

        # --------------------------------
        # Vision grounding
        # --------------------------------

        grounder = VisionGrounder()

        target = await grounder.locate(
            screenshot_path=screenshot_path,
            description="the Learn More link",
        )

        print("\nVISION TARGET:")
        print(target)

        # --------------------------------
        # Basic validation
        # --------------------------------

        assert target.found is True
        assert target.x is not None
        assert target.y is not None

        # --------------------------------
        # Compare vision vs DOM
        # --------------------------------

        print("\nGROUNDING COMPARISON:")

        print(
            "Vision coordinates:",
            target.x,
            target.y,
        )

        print(
            "DOM bounding box:",
            link_box,
        )

        print(
            "DOM center:",
            dom_center_x,
            dom_center_y,
        )

        # --------------------------------
        # Calculate grounding error
        # --------------------------------

        grounding_error = math.sqrt(
            (target.x - dom_center_x) ** 2
            + (target.y - dom_center_y) ** 2
        )

        print("\nGROUNDING ERROR:")
        print(
            f"{grounding_error:.2f}px"
        )

        # --------------------------------
        # Require reasonable visual accuracy
        # --------------------------------

        assert grounding_error < 100, (
            "Vision grounding is too far from "
            f"the actual element center. "
            f"Vision=({target.x}, {target.y}), "
            f"DOM=({dom_center_x:.2f}, "
            f"{dom_center_y:.2f}), "
            f"error={grounding_error:.2f}px"
        )

        # --------------------------------
        # Visual click
        # --------------------------------

        result = await tools.click_coordinates(
            target.x,
            target.y,
        )

        print("\nVISUAL CLICK:")
        print(result)

        # --------------------------------
        # Give navigation a moment
        # --------------------------------

        await page.wait_for_timeout(
            1500
        )

        print("\nFINAL URL:")
        print(page.url)

        # --------------------------------
        # Verify click
        # --------------------------------

        assert "iana.org" in page.url

    finally:
        await manager.close()