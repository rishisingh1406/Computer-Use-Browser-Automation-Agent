from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


class BrowserManager:
    """
    Manages the lifecycle of the Playwright browser.

    The agent should interact with the browser through
    BrowserTools rather than directly controlling Playwright.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self) -> Page:
        """Start Playwright, launch Chromium, and create a page."""

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless
        )

        self.context = await self.browser.new_context()

        self.page = await self.context.new_page()

        return self.page

    async def close(self) -> None:
        """Close the browser and stop Playwright."""

        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None