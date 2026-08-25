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

    async def navigate(self, url: str) -> dict:
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

    async def click(self, selector: str) -> dict:
        """Click an element using a CSS selector."""

        await self.page.locator(selector).click()

        return {
            "action": "click",
            "selector": selector,
            "url": self.page.url,
        }

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

    async def screenshot(
        self,
        path: str = "screenshots/page.png",
    ) -> dict:
        """Capture the current browser page."""

        output_path = Path(path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        await self.page.screenshot(
            path=str(output_path),
            full_page=True,
        )

        return {
            "action": "screenshot",
            "path": str(output_path),
        }

    async def read_text(self) -> dict:
        """Read visible text from the current page."""

        text = await self.page.locator("body").inner_text()

        return {
            "action": "read_text",
            "text": text,
        }

    async def scroll(
        self,
        direction: str = "down",
    ) -> dict:
        """Scroll the page up or down."""

        if direction == "down":
            await self.page.mouse.wheel(0, 800)

        elif direction == "up":
            await self.page.mouse.wheel(0, -800)

        else:
            raise ValueError(
                "direction must be 'up' or 'down'"
            )

        return {
            "action": "scroll",
            "direction": direction,
        }