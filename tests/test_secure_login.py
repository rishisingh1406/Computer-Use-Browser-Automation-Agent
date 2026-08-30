from app.agent.models import LoginCredentials
from app.auth.credentials import CredentialProvider
from app.auth.redaction import SecretRedactor
from app.agent.models import LoginCredentials
import pytest
from app.agent.models import LoginCredentials
from app.agent.login import SecureLoginExecutor
from app.agent.models import LoginCredentials


@pytest.mark.asyncio
async def test_password_not_returned(mock_browser_tools):

    credentials = LoginCredentials(
        username="test@example.com",
        password="SUPER_SECRET_PASSWORD",
    )

    executor = SecureLoginExecutor(
        mock_browser_tools
    )

    result = await executor.login(
        credentials=credentials,
        username_selector="#username",
        password_selector="#password",
        submit_selector="#submit",
    )

    serialized = str(result)

    assert "SUPER_SECRET_PASSWORD" not in serialized



def test_empty_username_rejected():
    with pytest.raises(ValueError):
        LoginCredentials(
            username="",
            password="secret",
        )


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        LoginCredentials(
            username="test@example.com",
            password="",
        )


def test_login_credentials():
    credentials = LoginCredentials(
        username="test@example.com",
        password="secret",
    )

    assert credentials.username == "test@example.com"
    assert credentials.password == "secret"


def test_credentials_validate():

    credentials = LoginCredentials(
        username="test_user",
        password="test_password",
    )

    assert credentials.username == "test_user"
    assert credentials.password == "test_password"


def test_empty_username_rejected():

    try:
        LoginCredentials(
            username="",
            password="secret",
        )
        assert False
    except ValueError:
        assert True


def test_empty_password_rejected():

    try:
        LoginCredentials(
            username="user",
            password="",
        )
        assert False
    except ValueError:
        assert True


def test_site_environment_mapping():

    provider = CredentialProvider()

    assert (
        provider._site_to_prefix("github.com")
        == "GITHUB_COM"
    )


def test_secret_redaction():

    redactor = SecretRedactor(
        secrets=[
            "test_user",
            "super_secret_password",
        ]
    )

    text = (
        "Username: test_user "
        "Password: super_secret_password"
    )

    result = redactor.redact(text)

    assert "test_user" not in result
    assert "super_secret_password" not in result

    assert "[REDACTED]" in result