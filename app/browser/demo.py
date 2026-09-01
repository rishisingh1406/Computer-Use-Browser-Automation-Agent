import asyncio
import os

from app.browser.manager import BrowserManager
from app.browser.tools import BrowserTools


async def main():

    headless = (
        os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    )

    manager = BrowserManager(
        headless=headless
    )

    try:

        page = await manager.start()

        tools = BrowserTools(page)

        print("\n--- NAVIGATE ---")

        result = await tools.navigate(
            "https://example.com"
        )

        print(result)

        print("\n--- READ TEXT ---")

        result = await tools.read_text()

        print(result["text"])

        print("\n--- SCREENSHOT ---")

        result = await tools.screenshot(
            "screenshots/example.png"
        )

        print(result)

    finally:

        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())