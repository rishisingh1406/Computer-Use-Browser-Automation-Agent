from app.security.guardrails import (
    DomainGuard,
    HumanConfirmationGate,
)


def build_domain_guard() -> DomainGuard:
    return DomainGuard(
        allowed_domains={
            "example.com",
            "example.org",
        }
    )


def build_confirmation_gate() -> HumanConfirmationGate:
    return HumanConfirmationGate(
        enabled=True,
    )