import pytest
from pydantic import ValidationError

from app.extraction.schemas import PricingPlan, PricingTable


# ==========================================================
# PRICING PLAN
# ==========================================================


def test_pricing_plan_valid():
    plan = PricingPlan(
        name="Pro",
        price=25,
        currency="USD",
        billing_period="month",
        description="Professional plan",
    )

    assert plan.name == "Pro"
    assert plan.price == 25
    assert plan.currency == "USD"
    assert plan.billing_period == "month"
    assert plan.description == "Professional plan"


def test_pricing_plan_defaults():
    plan = PricingPlan(name="Free")

    assert plan.name == "Free"
    assert plan.price is None
    assert plan.currency is None
    assert plan.billing_period is None
    assert plan.description is None


def test_pricing_plan_strips_name():
    plan = PricingPlan(name="  Pro  ")

    assert plan.name == "Pro"


def test_pricing_plan_rejects_empty_name():
    with pytest.raises(ValidationError):
        PricingPlan(name="   ")


def test_pricing_plan_rejects_negative_price():
    with pytest.raises(ValidationError):
        PricingPlan(
            name="Pro",
            price=-10,
        )


def test_pricing_plan_allows_zero_price():
    plan = PricingPlan(
        name="Free",
        price=0,
    )

    assert plan.price == 0


@pytest.mark.parametrize(
    "currency",
    [
        "USD",
        "EUR",
        "GBP",
        "INR",
    ],
)
def test_pricing_plan_accepts_supported_currency(currency):
    plan = PricingPlan(
        name="Pro",
        currency=currency,
    )

    assert plan.currency == currency


def test_pricing_plan_normalizes_currency():
    plan = PricingPlan(
        name="Pro",
        currency=" usd ",
    )

    assert plan.currency == "USD"


def test_pricing_plan_rejects_unsupported_currency():
    with pytest.raises(ValidationError):
        PricingPlan(
            name="Pro",
            currency="JPY",
        )


@pytest.mark.parametrize(
    "billing_period",
    [
        "month",
        "year",
        "week",
        "day",
    ],
)
def test_pricing_plan_accepts_supported_billing_period(
    billing_period,
):
    plan = PricingPlan(
        name="Pro",
        billing_period=billing_period,
    )

    assert plan.billing_period == billing_period


def test_pricing_plan_normalizes_billing_period():
    plan = PricingPlan(
        name="Pro",
        billing_period=" MONTH ",
    )

    assert plan.billing_period == "month"


def test_pricing_plan_rejects_unsupported_billing_period():
    with pytest.raises(ValidationError):
        PricingPlan(
            name="Pro",
            billing_period="quarter",
        )


# ==========================================================
# PRICING TABLE
# ==========================================================


def test_pricing_table_valid():
    table = PricingTable(
        site="example.com",
        product="Example",
        currency="USD",
        plans=[
            PricingPlan(
                name="Free",
                price=0,
                currency="USD",
            ),
            PricingPlan(
                name="Pro",
                price=20,
                currency="USD",
                billing_period="month",
            ),
        ],
    )

    assert table.site == "example.com"
    assert table.product == "Example"
    assert table.currency == "USD"
    assert len(table.plans) == 2


def test_pricing_table_defaults():
    table = PricingTable(
        site="example.com",
    )

    assert table.site == "example.com"
    assert table.product is None
    assert table.currency is None
    assert table.plans == []


def test_pricing_table_strips_site():
    table = PricingTable(
        site="  example.com  ",
    )

    assert table.site == "example.com"


def test_pricing_table_rejects_empty_site():
    with pytest.raises(ValidationError):
        PricingTable(site="   ")


def test_pricing_table_normalizes_currency():
    table = PricingTable(
        site="example.com",
        currency=" eur ",
    )

    assert table.currency == "EUR"


def test_pricing_table_rejects_unsupported_currency():
    with pytest.raises(ValidationError):
        PricingTable(
            site="example.com",
            currency="JPY",
        )


def test_pricing_table_accepts_multiple_plans():
    table = PricingTable(
        site="example.com",
        plans=[
            PricingPlan(name="Free", price=0),
            PricingPlan(name="Pro", price=20),
            PricingPlan(name="Enterprise", price=100),
        ],
    )

    assert len(table.plans) == 3
    assert table.plans[0].name == "Free"
    assert table.plans[1].name == "Pro"
    assert table.plans[2].name == "Enterprise"


def test_pricing_table_serializes_to_dict():
    table = PricingTable(
        site="example.com",
        product="Example",
        currency="USD",
        plans=[
            PricingPlan(
                name="Pro",
                price=20,
                currency="USD",
                billing_period="month",
            )
        ],
    )

    data = table.model_dump()

    assert data["site"] == "example.com"
    assert data["product"] == "Example"
    assert data["currency"] == "USD"
    assert len(data["plans"]) == 1
    assert data["plans"][0]["name"] == "Pro"
    assert data["plans"][0]["price"] == 20


def test_pricing_table_json_round_trip():
    table = PricingTable(
        site="example.com",
        product="Example",
        currency="USD",
        plans=[
            PricingPlan(
                name="Pro",
                price=20,
                currency="USD",
                billing_period="month",
            )
        ],
    )

    serialized = table.model_dump_json()
    restored = PricingTable.model_validate_json(serialized)

    assert restored == table