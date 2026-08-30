import os

from app.agent.models import LoginCredentials
from app.auth.sites import LOGIN_CONFIGS


class CredentialProvider:
    """
    Loads credentials from the runtime environment.

    Credentials never enter the LLM context.

    The environment-variable mapping comes from the trusted
    LOGIN_CONFIGS registry, not from the LLM.
    """

    def get_credentials(
        self,
        site: str,
    ) -> LoginCredentials:
        site = site.strip().lower()

        config = LOGIN_CONFIGS.get(site)

        if config is None:
            raise ValueError(
                f"No login configuration exists for site: {site}"
            )

        username = os.getenv(config.username_env)
        password = os.getenv(config.password_env)

        if username is None:
            raise RuntimeError(
                f"Missing required credential environment variable: "
                f"{config.username_env}"
            )

        if password is None:
            raise RuntimeError(
                f"Missing required credential environment variable: "
                f"{config.password_env}"
            )

        return LoginCredentials(
            username=username,
            password=password,
        )