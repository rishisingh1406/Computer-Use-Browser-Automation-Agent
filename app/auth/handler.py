from app.auth.credentials import CredentialProvider
from app.auth.login import LoginExecutor
from app.auth.sites import LOGIN_CONFIGS


class SecureLoginHandler:
    """
    Trusted orchestration layer for authenticated browser flows.

    Security boundary:

        Site
          ↓
        LoginConfig
          ↓
        CredentialProvider
          ↓
        LoginCredentials
          ↓
        LoginExecutor
          ↓
        BrowserTools / Playwright

    The LLM is completely outside this credential path.
    """

    def __init__(
        self,
        browser_tools,
        credential_provider: CredentialProvider | None = None,
        login_executor: LoginExecutor | None = None,
    ):
        self.browser_tools = browser_tools

        self.credential_provider = (
            credential_provider
            or CredentialProvider()
        )

        self.login_executor = (
            login_executor
            or LoginExecutor(browser_tools)
        )

    async def login(
        self,
        site: str,
    ) -> None:
        """
        Execute the trusted login flow for a configured site.

        Credentials are loaded internally and are never
        returned to the caller.
        """

        site = site.strip().lower()

        config = LOGIN_CONFIGS.get(site)

        if config is None:
            raise ValueError(
                f"No login configuration exists for site: {site}"
            )

        credentials = None

        try:
            credentials = (
                self.credential_provider.get_credentials(site)
            )

            await self.browser_tools.navigate(
                config.login_url
            )

            await self.login_executor.login(
                credentials=credentials,
                username_selector=config.username_selector,
                password_selector=config.password_selector,
                submit_selector=config.submit_selector,
            )

            await self.browser_tools.read_text()

            if config.success_url_contains:
                page = getattr(
                    self.browser_tools,
                    "page",
                    None,
                )

                if page is not None:
                    current_url = getattr(
                        page,
                        "url",
                        "",
                    )

                    if (
                        config.success_url_contains
                        not in current_url
                    ):
                        raise RuntimeError(
                            "Login completed but the expected "
                            "authenticated URL was not reached."
                        )

        except RuntimeError:
            raise

        except Exception as exc:
            raise RuntimeError(
                "Secure login execution failed."
            ) from exc

        finally:
            # Remove our local reference as soon as possible.
            credentials = None