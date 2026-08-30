from app.agent.models import LoginCredentials


class LoginExecutor:
    """
    Trusted authentication execution layer.

    Credentials are injected directly into browser fields.

    IMPORTANT:
        - Credentials must never be sent to the LLM.
        - Credentials must never be returned.
        - Passwords must never be logged.
        - Credentials must never appear in exceptions.
    """

    def __init__(self, browser_tools):
        self.browser_tools = browser_tools

    async def login(
        self,
        credentials: LoginCredentials,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
    ) -> None:
        """
        Perform login using runtime-provided credentials.

        Credentials remain inside this trusted execution
        boundary.
        """

        try:
            await self.browser_tools.type_text(
                username_selector,
                credentials.username,
            )

            await self.browser_tools.type_text(
                password_selector,
                credentials.password,
            )

            await self.browser_tools.click(
                submit_selector,
            )

        except Exception as exc:
            raise RuntimeError(
                "Secure login execution failed."
            ) from exc