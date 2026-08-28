from pydantic import BaseModel, Field, field_validator


class PricingPlan(BaseModel):
    """
    Normalized representation of one pricing plan.
    """

    name: str

    price: float | None = None

    currency: str | None = None

    billing_period: str | None = None

    description: str | None = None

    # ==========================================================
    # NAME VALIDATION
    # ==========================================================

    @field_validator("name")
    @classmethod
    def validate_name(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "PricingPlan name cannot be empty."
            )

        return value

    # ==========================================================
    # PRICE VALIDATION
    # ==========================================================

    @field_validator("price")
    @classmethod
    def validate_price(
        cls,
        value: float | None,
    ) -> float | None:

        if value is None:
            return None

        if value < 0:
            raise ValueError(
                "PricingPlan price cannot be negative."
            )

        return value

    # ==========================================================
    # CURRENCY VALIDATION
    # ==========================================================

    @field_validator("currency")
    @classmethod
    def validate_currency(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip().upper()

        allowed = {
            "USD",
            "EUR",
            "GBP",
            "INR",
        }

        if value not in allowed:
            raise ValueError(
                f"Unsupported currency: {value}"
            )

        return value

    # ==========================================================
    # BILLING PERIOD VALIDATION
    # ==========================================================

    @field_validator("billing_period")
    @classmethod
    def validate_billing_period(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip().lower()

        allowed = {
            "month",
            "year",
            "week",
            "day",
        }

        if value not in allowed:
            raise ValueError(
                f"Unsupported billing period: {value}"
            )

        return value


class PricingTable(BaseModel):
    """
    Normalized pricing information extracted
    from a website.
    """

    site: str

    product: str | None = None

    currency: str | None = None

    plans: list[PricingPlan] = Field(
        default_factory=list
    )

    # ==========================================================
    # SITE VALIDATION
    # ==========================================================

    @field_validator("site")
    @classmethod
    def validate_site(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "PricingTable site cannot be empty."
            )

        return value

    # ==========================================================
    # CURRENCY VALIDATION
    # ==========================================================

    @field_validator("currency")
    @classmethod
    def validate_currency(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip().upper()

        allowed = {
            "USD",
            "EUR",
            "GBP",
            "INR",
        }

        if value not in allowed:
            raise ValueError(
                f"Unsupported currency: {value}"
            )

        return value

