import pytest

from app.security.guardrails import (
    DomainGuard,
    HumanConfirmationGate,
)


# ==========================================================
# DOMAIN GUARD - BASIC ALLOW
# ==========================================================


def test_domain_guard_allows_exact_domain():
    guard = DomainGuard(
        {"example.com"}
    )

    assert guard.is_allowed(
        "https://example.com"
    )


def test_domain_guard_allows_subdomain():
    guard = DomainGuard(
        {"example.com"}
    )

    assert guard.is_allowed(
        "https://shop.example.com"
    )


def test_domain_guard_allows_deep_subdomain():
    guard = DomainGuard(
        {"example.com"}
    )

    assert guard.is_allowed(
        "https://login.shop.example.com"
    )


# ==========================================================
# DOMAIN GUARD - DOMAIN BYPASS ATTACKS
# ==========================================================


def test_domain_guard_rejects_unrelated_domain():
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(
        "https://evil.com"
    )


def test_domain_guard_rejects_prefix_domain():
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(
        "https://evilexample.com"
    )


def test_domain_guard_rejects_suffix_attack():
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(
        "https://example.com.evil.com"
    )


def test_domain_guard_rejects_similar_domain():
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(
        "https://example.co"
    )


# ==========================================================
# DOMAIN GUARD - SCHEMES
# ==========================================================


def test_domain_guard_allows_http():
    guard = DomainGuard(
        {"example.com"}
    )

    assert guard.is_allowed(
        "http://example.com"
    )


def test_domain_guard_allows_https():
    guard = DomainGuard(
        {"example.com"}
    )

    assert guard.is_allowed(
        "https://example.com"
    )


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<h1>test</h1>",
        "file:///etc/passwd",
        "ftp://example.com",
    ],
)
def test_domain_guard_rejects_unsafe_schemes(
    url,
):
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(url)


# ==========================================================
# DOMAIN GUARD - CREDENTIALS
# ==========================================================


def test_domain_guard_rejects_username():
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(
        "https://user@example.com"
    )


def test_domain_guard_rejects_password():
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(
        "https://user:password@example.com"
    )


# ==========================================================
# DOMAIN GUARD - PORTS
# ==========================================================


def test_domain_guard_allows_valid_port():
    guard = DomainGuard(
        {"example.com"}
    )

    assert guard.is_allowed(
        "https://example.com:8443"
    )


def test_domain_guard_rejects_invalid_port():
    guard = DomainGuard(
        {"example.com"}
    )

    assert not guard.is_allowed(
        "https://example.com:invalid"
    )


# ==========================================================
# DOMAIN GUARD - NORMALIZATION
# ==========================================================


def test_domain_guard_normalizes_case():
    guard = DomainGuard(
        {"EXAMPLE.COM"}
    )

    assert guard.is_allowed(
        "https://example.com"
    )


def test_domain_guard_normalizes_trailing_dot():
    guard = DomainGuard(
        {"example.com."}
    )

    assert guard.is_allowed(
        "https://example.com"
    )


def test_domain_guard_accepts_http_url_as_allowlist_entry():
    guard = DomainGuard(
        {"https://example.com"}
    )

    assert guard.is_allowed(
        "https://example.com"
    )


def test_domain_guard_rejects_wildcard():
    with pytest.raises(ValueError):
        DomainGuard(
            {"*.example.com"}
        )


def test_domain_guard_rejects_empty_allowlist():
    with pytest.raises(ValueError):
        DomainGuard(set())


# ==========================================================
# DOMAIN GUARD - VALIDATE
# ==========================================================


def test_validate_returns_original_url():
    guard = DomainGuard(
        {"example.com"}
    )

    url = "https://example.com/products?page=1"

    assert guard.validate(url) == url


def test_validate_raises_for_disallowed_domain():
    guard = DomainGuard(
        {"example.com"}
    )

    with pytest.raises(
        ValueError,
        match="not allowed",
    ):
        guard.validate(
            "https://evil.com"
        )


def test_validate_raises_for_invalid_scheme():
    guard = DomainGuard(
        {"example.com"}
    )

    with pytest.raises(
        ValueError,
        match="scheme",
    ):
        guard.validate(
            "javascript:alert(1)"
        )


def test_validate_raises_for_credentials():
    guard = DomainGuard(
        {"example.com"}
    )

    with pytest.raises(
        ValueError,
        match="username or password",
    ):
        guard.validate(
            "https://admin:secret@example.com"
        )


# ==========================================================
# HUMAN CONFIRMATION GATE
# ==========================================================


@pytest.mark.asyncio
async def test_confirmation_gate_accepts_yes():

    gate = HumanConfirmationGate(
        input_func=lambda _: "yes"
    )

    result = await gate.confirm(
        action="click",
        url="https://example.com",
        description="Submit form",
    )

    assert result is True


@pytest.mark.asyncio
async def test_confirmation_gate_accepts_y():

    gate = HumanConfirmationGate(
        input_func=lambda _: "y"
    )

    result = await gate.confirm(
        action="click",
        url="https://example.com",
        description="Submit form",
    )

    assert result is True


@pytest.mark.asyncio
async def test_confirmation_gate_rejects_no():

    gate = HumanConfirmationGate(
        input_func=lambda _: "no"
    )

    result = await gate.confirm(
        action="click",
        url="https://example.com",
        description="Submit form",
    )

    assert result is False


@pytest.mark.asyncio
async def test_confirmation_gate_rejects_empty_input():

    gate = HumanConfirmationGate(
        input_func=lambda _: ""
    )

    result = await gate.confirm(
        action="click",
        url="https://example.com",
        description="Submit form",
    )

    assert result is False


@pytest.mark.asyncio
async def test_confirmation_gate_is_case_insensitive():

    gate = HumanConfirmationGate(
        input_func=lambda _: "YES"
    )

    result = await gate.confirm(
        action="click",
        url="https://example.com",
        description="Submit form",
    )

    assert result is True


@pytest.mark.asyncio
async def test_confirmation_gate_denies_eof():

    def raise_eof(_):
        raise EOFError

    gate = HumanConfirmationGate(
        input_func=raise_eof
    )

    result = await gate.confirm(
        action="click",
        url="https://example.com",
        description="Submit form",
    )

    assert result is False


@pytest.mark.asyncio
async def test_confirmation_gate_rejects_empty_action():

    gate = HumanConfirmationGate(
        input_func=lambda _: "yes"
    )

    with pytest.raises(
        ValueError,
        match="action cannot be empty",
    ):
        await gate.confirm(
            action="",
            url="https://example.com",
            description="Submit form",
        )


@pytest.mark.asyncio
async def test_confirmation_gate_rejects_empty_url():

    gate = HumanConfirmationGate(
        input_func=lambda _: "yes"
    )

    with pytest.raises(
        ValueError,
        match="URL cannot be empty",
    ):
        await gate.confirm(
            action="click",
            url="",
            description="Submit form",
        )


@pytest.mark.asyncio
async def test_confirmation_gate_rejects_empty_description():

    gate = HumanConfirmationGate(
        input_func=lambda _: "yes"
    )

    with pytest.raises(
        ValueError,
        match="description cannot be empty",
    ):
        await gate.confirm(
            action="click",
            url="https://example.com",
            description="",
        )