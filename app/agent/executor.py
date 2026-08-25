from app.agent.models import BrowserAction
from app.browser.tools import BrowserTools


class ActionExecutor:

    def __init__(self, browser_tools: BrowserTools):
        self.browser_tools = browser_tools

    async def execute(
        self,
        action: BrowserAction,
    ) -> dict:

        if action.action == "navigate":
            if not action.url:
                raise ValueError(
                    "navigate requires a URL"
                )

            return await self.browser_tools.navigate(
                action.url
            )

        if action.action == "click":
            if not action.selector:
                raise ValueError(
                    "click requires a selector"
                )

            return await self.browser_tools.click(
                action.selector
            )

        if action.action == "type":
            if not action.selector:
                raise ValueError(
                    "type requires a selector"
                )

            if action.text is None:
                raise ValueError(
                    "type requires text"
                )

            return await self.browser_tools.type_text(
                action.selector,
                action.text,
            )

        if action.action == "scroll":
            if not action.direction:
                raise ValueError(
                    "scroll requires a direction"
                )

            return await self.browser_tools.scroll(
                action.direction
            )

        if action.action == "done":
            return {
                "action": "done",
                "status": "complete",
            }

        raise ValueError(
            f"Unsupported action: {action.action}"
        )
