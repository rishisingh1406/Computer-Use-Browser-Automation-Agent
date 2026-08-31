from __future__ import annotations

from urllib.parse import urlparse


class DomainGuard:
    """
    Controls which domains the browser agent is allowed to visit.

    Security model:

        Allowed:
            example.com
            shop.example.com
            login.example.com

        Rejected:
            evil.com
            example.com.evil.com
            evilexample.com
            javascript:...
            data:...
            file:...
            ftp:...
            URLs containing credentials/userinfo

    The allow-list contains trusted registrable domains such as:

        {"example.com", "github.com"}

    A domain automatically allows its subdomains.
    """

    ALLOWED_SCHEMES = {
        "http",
        "https",
    }

    def __init__(
        self,
        allowed_domains: set[str] | list[str] | tuple[str, ...],
    ):
        if not allowed_domains:
            raise ValueError(
                "Domain allow-list cannot be empty."
            )

        self.allowed_domains = {
            self._normalize_domain(domain)
            for domain in allowed_domains
        }

    # ==========================================================
    # DOMAIN NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_domain(
        domain: str,
    ) -> str:
        """
        Normalize an allow-listed domain.

        Examples:

            "example.com"       -> "example.com"
            "EXAMPLE.COM"       -> "example.com"
            "example.com/"      -> rejected
            "https://example.com" -> "example.com"
        """

        if not isinstance(domain, str):
            raise ValueError(
                "Allowed domain must be a string."
            )

        domain = domain.strip().lower()

        if not domain:
            raise ValueError(
                "Allowed domain cannot be empty."
            )

        # Allow full HTTP/HTTPS URLs as input.
        if "://" in domain:
            parsed = urlparse(domain)

            if parsed.scheme not in DomainGuard.ALLOWED_SCHEMES:
                raise ValueError(
                    f"Unsupported domain scheme: {parsed.scheme}"
                )

            if (
                parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError(
                    "Allowed domain must not contain credentials."
                )

            if not parsed.hostname:
                raise ValueError(
                    "Allowed domain must contain a hostname."
                )

            # An allow-list entry must not contain a path/query/etc.
            if parsed.path not in ("", "/"):
                raise ValueError(
                    "Allowed domain must not contain a path."
                )

            if parsed.query:
                raise ValueError(
                    "Allowed domain must not contain a query."
                )

            if parsed.fragment:
                raise ValueError(
                    "Allowed domain must not contain a fragment."
                )

            domain = parsed.hostname.lower()

        else:
            # Remove trailing DNS dot.
            domain = domain.rstrip(".")

            # Paths are not valid in an allow-list entry.
            if "/" in domain:
                raise ValueError(
                    f"Invalid allowed domain: {domain}"
                )

            # Ports are not part of the domain.
            if ":" in domain:
                raise ValueError(
                    f"Invalid allowed domain: {domain}"
                )

        domain = domain.rstrip(".")

        if not domain:
            raise ValueError(
                "Allowed domain cannot be empty."
            )

        # Wildcards are intentionally unsupported.
        if "*" in domain:
            raise ValueError(
                "Wildcard domains are not supported."
            )

        return domain

    # ==========================================================
    # URL VALIDATION
    # ==========================================================

    def validate(
        self,
        url: str,
    ) -> str:
        """
        Validate a URL against the domain allow-list.

        Returns:
            The original normalized URL string.

        Raises:
            ValueError: if the URL is invalid or disallowed.
        """

        if not isinstance(url, str):
            raise ValueError(
                "URL must be a string."
            )

        url = url.strip()

        if not url:
            raise ValueError(
                "URL cannot be empty."
            )

        parsed = urlparse(url)

        # ------------------------------------------------------
        # Scheme
        # ------------------------------------------------------

        scheme = parsed.scheme.lower()

        if scheme not in self.ALLOWED_SCHEMES:
            raise ValueError(
                f"URL scheme '{parsed.scheme}' is not allowed. "
                "Only http and https are permitted."
            )

        # ------------------------------------------------------
        # Hostname
        # ------------------------------------------------------

        hostname = parsed.hostname

        if not hostname:
            raise ValueError(
                "URL must contain a valid hostname."
            )

        hostname = hostname.lower().rstrip(".")

        # ------------------------------------------------------
        # Credentials / userinfo
        # ------------------------------------------------------

        if (
            parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError(
                "URLs containing username or password "
                "information are not allowed."
            )

        # ------------------------------------------------------
        # Port validation
        # ------------------------------------------------------

        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError(
                "URL contains an invalid port."
            ) from exc

        # ------------------------------------------------------
        # Domain allow-list
        # ------------------------------------------------------

        if not self._domain_matches_allow_list(hostname):
            raise ValueError(
                f"Domain '{hostname}' is not allowed."
            )

        return url

    # ==========================================================
    # DOMAIN MATCHING
    # ==========================================================

    def _domain_matches_allow_list(
        self,
        hostname: str,
    ) -> bool:
        """
        Determine whether hostname belongs to an allowed domain.

        Examples:

            example.com
                -> allowed

            shop.example.com
                -> allowed

            login.shop.example.com
                -> allowed

            example.com.evil.com
                -> rejected

            notexample.com
                -> rejected
        """

        hostname = hostname.lower().rstrip(".")

        for allowed_domain in self.allowed_domains:

            if hostname == allowed_domain:
                return True

            # Critical security boundary:
            #
            #     shop.example.com
            #
            # matches:
            #
            #     .example.com
            #
            # but:
            #
            #     example.com.evil.com
            #
            # does not.

            if hostname.endswith(
                "." + allowed_domain
            ):
                return True

        return False

    # ==========================================================
    # PUBLIC CHECK
    # ==========================================================

    def is_allowed(
        self,
        url: str,
    ) -> bool:
        """
        Return True when the URL is allowed.

        Unlike validate(), this method does not raise for
        ordinary validation failures.
        """

        try:
            self.validate(url)
            return True

        except ValueError:
            return False


class HumanConfirmationGate:
    """
    Human-in-the-loop confirmation gate.

    Intended to protect potentially dangerous actions such as:

        - submitting forms
        - placing orders
        - sending messages
        - deleting data
        - making purchases
        - publishing content
        - other external side effects

    Only "y" or "yes" is treated as approval.

    Everything else is denied.
    """

    APPROVED_RESPONSES = {
        "y",
        "yes",
    }

    def __init__(
        self,
        input_func=None,
    ):
        """
        Create a confirmation gate.

        input_func is injectable for testing.
        """

        if input_func is None:
            input_func = input

        self.input_func = input_func

    # ==========================================================
    # CONFIRMATION
    # ==========================================================

    async def confirm(
        self,
        action: str,
        url: str,
        description: str,
    ) -> bool:
        """
        Ask a human whether a potentially dangerous action
        should be executed.

        Returns:

            True  -> explicitly approved
            False -> denied
        """

        if not isinstance(action, str):
            raise ValueError(
                "Confirmation action must be a string."
            )

        if not isinstance(url, str):
            raise ValueError(
                "Confirmation URL must be a string."
            )

        if not isinstance(description, str):
            raise ValueError(
                "Confirmation description must be a string."
            )

        action = action.strip()
        url = url.strip()
        description = description.strip()

        if not action:
            raise ValueError(
                "Confirmation action cannot be empty."
            )

        if not url:
            raise ValueError(
                "Confirmation URL cannot be empty."
            )

        if not description:
            raise ValueError(
                "Confirmation description cannot be empty."
            )

        print()
        print("=" * 60)
        print("HUMAN CONFIRMATION REQUIRED")
        print("=" * 60)
        print(f"Action:      {action}")
        print(f"URL:         {url}")
        print(f"Description: {description}")
        print()

        print(
            "This action may cause an external side effect."
        )

        print(
            "Approve only if you intentionally want "
            "the action to proceed."
        )

        print()

        try:
            response = self.input_func(
                "Approve action? [y/N]: "
            )

        except (EOFError, KeyboardInterrupt):
            print(
                "\nHuman confirmation unavailable. "
                "Action denied."
            )
            return False

        if response is None:
            return False

        response = str(response).strip().lower()

        approved = (
            response in self.APPROVED_RESPONSES
        )

        if approved:
            print(
                "Human confirmation: APPROVED"
            )
        else:
            print(
                "Human confirmation: DENIED"
            )

        return approved