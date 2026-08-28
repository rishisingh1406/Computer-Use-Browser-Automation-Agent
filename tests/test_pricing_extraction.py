from app.extraction.pricing import PricingExtractor


# ==========================================================
# GITHUB COPILOT
# ==========================================================


def test_extract_github_copilot_pricing():

    text = """
    GitHub Copilot

    Free
    $0 USD per user / month

    Pro
    $10 USD per user / month

    Pro+
    $39 USD per user / month

    Max
    $100 USD per user / month

    Business
    $19 USD per user / month

    Enterprise
    $39 USD per user / month
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="github.com",
        product="GitHub Copilot",
        text=text,
    )

    assert result.site == "github.com"
    assert result.product == "GitHub Copilot"
    assert result.currency == "USD"

    assert len(result.plans) == 6

    prices = {
        plan.name: plan.price
        for plan in result.plans
    }

    assert prices["Free"] == 0
    assert prices["Pro"] == 10
    assert prices["Pro+"] == 39
    assert prices["Max"] == 100
    assert prices["Business"] == 19
    assert prices["Enterprise"] == 39


# ==========================================================
# BILLING PERIOD
# ==========================================================


def test_extract_billing_period():

    text = """
    Basic
    $10 USD per month

    Pro
    $100 USD per year
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text=text,
    )

    assert len(result.plans) == 2

    assert result.plans[0].billing_period == "month"
    assert result.plans[1].billing_period == "year"


# ==========================================================
# CURRENCY SYMBOLS
# ==========================================================


def test_extract_currency_symbols():

    extractor = PricingExtractor()

    usd = extractor.extract(
        site="example.com",
        product="Example",
        text="""
        Basic
        $10 per month
        """,
    )

    eur = extractor.extract(
        site="example.com",
        product="Example",
        text="""
        Basic
        €10 per month
        """,
    )

    gbp = extractor.extract(
        site="example.com",
        product="Example",
        text="""
        Basic
        £10 per month
        """,
    )

    inr = extractor.extract(
        site="example.com",
        product="Example",
        text="""
        Basic
        ₹999 per month
        """,
    )

    assert usd.currency == "USD"
    assert eur.currency == "EUR"
    assert gbp.currency == "GBP"
    assert inr.currency == "INR"


# ==========================================================
# CURRENCY CODES
# ==========================================================


def test_extract_currency_codes():

    text = """
    Basic
    10 EUR per month

    Pro
    20 EUR per month
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text=text,
    )

    assert result.currency == "EUR"

    assert result.plans[0].currency == "EUR"
    assert result.plans[1].currency == "EUR"


# ==========================================================
# FREE PLAN
# ==========================================================


def test_extract_free_plan():

    text = """
    Free
    $0 USD

    Pro
    $20 USD per month
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text=text,
    )

    assert len(result.plans) == 2

    assert result.plans[0].name == "Free"
    assert result.plans[0].price == 0
    assert result.plans[0].currency == "USD"

    assert result.plans[1].name == "Pro"
    assert result.plans[1].price == 20
    assert result.plans[1].currency == "USD"


# ==========================================================
# DECIMAL PRICES
# ==========================================================


def test_extract_decimal_price():

    text = """
    Pro
    $25.50 USD per month
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text=text,
    )

    assert len(result.plans) == 1
    assert result.plans[0].price == 25.50


# ==========================================================
# EMPTY TEXT
# ==========================================================


def test_empty_text_returns_empty_pricing_table():

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text="",
    )

    assert result.site == "example.com"
    assert result.product == "Example"
    assert result.currency is None
    assert result.plans == []


# ==========================================================
# WHITESPACE TEXT
# ==========================================================


def test_whitespace_text_returns_empty_pricing_table():

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text="   \n   \n",
    )

    assert result.plans == []


# ==========================================================
# DESCRIPTION
# ==========================================================


def test_price_line_is_preserved_as_description():

    text = """
    Pro
    $25 USD per user / month
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text=text,
    )

    assert len(result.plans) == 1

    assert (
        result.plans[0].description
        == "$25 USD per user / month"
    )


# ==========================================================
# IGNORE PRICING HEADINGS
# ==========================================================


def test_pricing_heading_is_not_treated_as_plan():

    text = """
    Pricing

    Pro
    $25 USD per month
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text=text,
    )

    assert len(result.plans) == 1
    assert result.plans[0].name == "Pro"


# ==========================================================
# DUPLICATE PLAN
# ==========================================================


def test_duplicate_plan_is_removed():

    text = """
    Pro
    $25 USD per month

    Pro
    $25 USD per month
    """

    extractor = PricingExtractor()

    result = extractor.extract(
        site="example.com",
        product="Example",
        text=text,
    )

    assert len(result.plans) == 1

    assert result.plans[0].name == "Pro"
    assert result.plans[0].price == 25

