import os

from playwright.async_api import async_playwright


class BrowserManager:
    """
    Manages the Playwright browser lifecycle.

    Headless mode can be supplied explicitly or controlled
    through the BROWSER_HEADLESS environment variable.
    """

    def __init__(self, headless: bool | None = None):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

        if headless is None:
            self.headless = (
                os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
            )
        else:
            self.headless = headless

    async def start(self):
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless
        )

        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

        return self.page

    async def stop(self):
        if self.page:
            await self.page.close()
            self.page = None

        if self.context:
            await self.context.close()
            self.context = None

        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def close(self):
        """
        Backwards-compatible alias for stop().
        """
        await self.stop()