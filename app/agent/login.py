from app.agent.models import LoginCredentials
from app.browser.tools import BrowserTools


class SecureLoginExecutor:
    """
    Executes login using runtime-supplied credentials.

    IMPORTANT:
        Credentials never enter the LLM.
        Passwords are never logged.
        Passwords are never returned in results.
    """

    def __init__(
        self,
        browser_tools: BrowserTools,
    ):
        self.browser_tools = browser_tools

    async def login(
        self,
        credentials: LoginCredentials,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
    ) -> dict:

        await self.browser_tools.type_text(
            username_selector,
            credentials.username,
        )

        await self.browser_tools.type_text(
            password_selector,
            credentials.password,
        )

        result = await self.browser_tools.click(
            submit_selector
        )

        return {
            "action": "login",
            "status": "submitted",
            "username_filled": True,
            "password_filled": True,
            "submit_result": result,
        }