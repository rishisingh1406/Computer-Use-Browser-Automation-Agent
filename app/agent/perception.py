from pathlib import Path

from app.agent.models import BrowserObservation
from app.browser.tools import BrowserTools


class Perception:

    def __init__(self, browser_tools: BrowserTools):
        self.browser_tools = browser_tools

    async def observe(self) -> BrowserObservation:
        page = self.browser_tools.page

        text_result = await self.browser_tools.read_text()

        screenshot_path = (
            Path("screenshots")
            / "agent_observation.png"
        )

        await self.browser_tools.screenshot(
            str(screenshot_path)
        )

        return BrowserObservation(
            url=page.url,
            title=await page.title(),
            text=text_result["text"],
            screenshot_path=str(screenshot_path),
        )
