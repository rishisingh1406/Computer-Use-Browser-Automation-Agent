import re

from app.extraction.schemas import PricingPlan, PricingTable


class PricingExtractor:
    """
    Deterministic pricing extractor.

    Converts raw visible webpage text into a normalized
    PricingTable without using an LLM.
    """

    # ----------------------------------------------------------
    # PRICE PATTERNS
    # ----------------------------------------------------------

    PRICE_PATTERN = re.compile(
        r"""
        (?:
            (?P<symbol>[$€£₹])
            \s*
        )
        (?P<amount>\d+(?:[.,]\d+)?)
        |
        (?P<amount_code>\d+(?:[.,]\d+)?)
        \s*
        (?P<currency>USD|EUR|GBP|INR)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # ----------------------------------------------------------
    # CURRENCY NORMALIZATION
    # ----------------------------------------------------------

    CURRENCY_SYMBOLS = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "₹": "INR",
    }

    CURRENCY_NAMES = {
        "USD": "USD",
        "EUR": "EUR",
        "GBP": "GBP",
        "INR": "INR",
    }

    # ----------------------------------------------------------
    # COMMON NON-PLAN HEADINGS
    # ----------------------------------------------------------

    IGNORED_PLAN_NAMES = {
        "pricing",
        "plans",
        "plan",
        "pricing plans",
        "pricing options",
        "features",
        "features include",
        "features included",
        "compare plans",
        "compare pricing",
        "monthly",
        "yearly",
        "annual",
        "annually",
        "per user",
        "per month",
        "per year",
        "per week",
        "per day",
    }

    # ----------------------------------------------------------
    # EXTRACT
    # ----------------------------------------------------------

    def extract(
        self,
        site: str,
        product: str | None,
        text: str,
    ) -> PricingTable:
        """
        Extract normalized pricing information from raw
        visible webpage text.
        """

        if not text or not text.strip():
            return PricingTable(
                site=site,
                product=product,
                currency=None,
                plans=[],
            )

        lines = self._clean_lines(text)

        plans: list[PricingPlan] = []

        for index, line in enumerate(lines):

            price_match = self._find_price(line)

            if price_match is None:
                continue

            price, currency, billing_period = price_match

            plan_name = self._find_plan_name(
                lines=lines,
                price_index=index,
            )

            if not plan_name:
                continue

            description = self._build_description(
                line=line,
                plan_name=plan_name,
            )

            plans.append(
                PricingPlan(
                    name=plan_name,
                    price=price,
                    currency=currency,
                    billing_period=billing_period,
                    description=description,
                )
            )

        # ------------------------------------------------------
        # Remove accidental duplicate plans
        # ------------------------------------------------------

        plans = self._deduplicate_plans(plans)

        # ------------------------------------------------------
        # Infer table-level currency
        # ------------------------------------------------------

        currency = self._infer_currency(
            plans=plans,
            text=text,
        )

        return PricingTable(
            site=site,
            product=product,
            currency=currency,
            plans=plans,
        )

    # ==========================================================
    # CLEAN INPUT
    # ==========================================================

    @staticmethod
    def _clean_lines(
        text: str,
    ) -> list[str]:
        """
        Normalize raw webpage text into meaningful lines.
        """

        return [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

    # ==========================================================
    # PRICE EXTRACTION
    # ==========================================================

    def _find_price(
        self,
        line: str,
    ) -> tuple[
        float,
        str | None,
        str | None,
    ] | None:
        """
        Extract a price from a line.

        Supported:

            $10
            $10 USD
            €20
            £30
            ₹999
            10 USD
            25.50 USD
            25,50 EUR

        Important:
            A plain number such as "2,000 CI/CD minutes"
            is NOT considered a price.

        This prevents unrelated webpage numbers from becoming
        pricing plans.
        """

        match = self.PRICE_PATTERN.search(line)

        if not match:
            return None

        # ------------------------------------------------------
        # Amount
        # ------------------------------------------------------

        amount_text = (
            match.group("amount")
            or match.group("amount_code")
        )

        if not amount_text:
            return None

        amount_text = amount_text.replace(",", ".")

        try:
            price = float(amount_text)

        except ValueError:
            return None

        # ------------------------------------------------------
        # Currency
        # ------------------------------------------------------

        symbol = match.group("symbol")
        currency_code = match.group("currency")

        currency = None

        if currency_code:
            currency = self.CURRENCY_NAMES.get(
                currency_code.upper()
            )

        elif symbol:
            currency = self.CURRENCY_SYMBOLS.get(
                symbol
            )

        # ------------------------------------------------------
        # Billing period
        # ------------------------------------------------------

        billing_period = self._extract_billing_period(
            line
        )

        return (
            price,
            currency,
            billing_period,
        )

    # ==========================================================
    # BILLING PERIOD
    # ==========================================================

    @staticmethod
    def _extract_billing_period(
        line: str,
    ) -> str | None:
        """
        Detect common billing periods.
        """

        normalized = line.lower()

        if re.search(
            r"\b(month|monthly)\b",
            normalized,
        ):
            return "month"

        if re.search(
            r"\b(year|yearly|annual|annually)\b",
            normalized,
        ):
            return "year"

        if re.search(
            r"\b(week|weekly)\b",
            normalized,
        ):
            return "week"

        if re.search(
            r"\b(day|daily)\b",
            normalized,
        ):
            return "day"

        return None

    # ==========================================================
    # PLAN NAME
    # ==========================================================

    def _find_plan_name(
        self,
        lines: list[str],
        price_index: int,
    ) -> str | None:
        """
        Find the pricing-plan name immediately before
        the price line.

        Example:

            Pro
            $10 USD per user / month

        returns:

            Pro
        """

        if price_index == 0:
            return None

        candidate = lines[
            price_index - 1
        ].strip()

        if self._looks_like_plan_name(
            candidate
        ):
            return candidate

        return None

    # ==========================================================
    # PLAN NAME VALIDATION
    # ==========================================================

    def _looks_like_plan_name(
        self,
        text: str,
    ) -> bool:
        """
        Determine whether a line looks like a pricing-plan
        name rather than a heading or description.
        """

        if not text:
            return False

        # A plan name should not contain a price.
        if self.PRICE_PATTERN.search(text):
            return False

        normalized = re.sub(
            r"\s+",
            " ",
            text.lower(),
        ).strip()

        if normalized in self.IGNORED_PLAN_NAMES:
            return False

        # Avoid accepting very long paragraphs.
        if len(text) > 100:
            return False

        # Avoid sentence-like descriptions.
        if text.endswith(
            (".", ":", ";")
        ):
            return False

        return True

    # ==========================================================
    # DESCRIPTION
    # ==========================================================

    @staticmethod
    def _build_description(
        line: str,
        plan_name: str,
    ) -> str | None:
        """
        Preserve useful text from the price line.
        """

        description = line.strip()

        if not description:
            return None

        if (
            description.lower()
            == plan_name.lower()
        ):
            return None

        return description

    # ==========================================================
    # DEDUPLICATION
    # ==========================================================

    @staticmethod
    def _deduplicate_plans(
        plans: list[PricingPlan],
    ) -> list[PricingPlan]:
        """
        Remove duplicate plan entries while preserving
        their original order.
        """

        seen: set[
            tuple[
                str,
                float | None,
                str | None,
                str | None,
            ]
        ] = set()

        unique_plans: list[PricingPlan] = []

        for plan in plans:

            key = (
                plan.name.lower().strip(),
                plan.price,
                plan.currency,
                plan.billing_period,
            )

            if key in seen:
                continue

            seen.add(key)
            unique_plans.append(plan)

        return unique_plans

    # ==========================================================
    # CURRENCY INFERENCE
    # ==========================================================

    def _infer_currency(
        self,
        plans: list[PricingPlan],
        text: str,
    ) -> str | None:
        """
        Determine the dominant currency.

        Priority:

        1. Currency attached directly to a plan.
        2. Explicit currency code anywhere in text.
        3. Currency symbol anywhere in text.
        """

        # ------------------------------------------------------
        # 1. Currency attached to extracted plans
        # ------------------------------------------------------

        for plan in plans:

            if plan.currency:
                return plan.currency

        # ------------------------------------------------------
        # 2. Explicit currency codes
        # ------------------------------------------------------

        upper_text = text.upper()

        for currency in (
            "USD",
            "EUR",
            "GBP",
            "INR",
        ):

            if re.search(
                rf"\b{currency}\b",
                upper_text,
            ):
                return currency

        # ------------------------------------------------------
        # 3. Currency symbols
        # ------------------------------------------------------

        for symbol, currency in (
            self.CURRENCY_SYMBOLS.items()
        ):

            if symbol in text:
                return currency

        return None
