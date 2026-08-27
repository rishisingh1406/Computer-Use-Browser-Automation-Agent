import pytest

from app.agent.models import (
    BrowserPlan,
    PlanStep,
)

from app.agent.planner import PerSitePlanner


# ==========================================================
# TEST DATA
# ==========================================================


def make_plan() -> BrowserPlan:
    return BrowserPlan(
        goal="Get pricing",
        site="https://example.com",
        steps=[
            PlanStep(
                step_id=1,
                action="navigate",
                description="Navigate to the website",
                target="https://example.com",
                expected_result="Homepage loaded",
            ),
            PlanStep(
                step_id=2,
                action="search",
                description="Find the pricing page",
                target="pricing",
                expected_result="Pricing page found",
            ),
            PlanStep(
                step_id=3,
                action="extract",
                description="Extract pricing information",
                target="pricing",
                expected_result="Pricing extracted",
            ),
        ],
    )


# ==========================================================
# BASIC MODEL TESTS
# ==========================================================


def test_plan_model():

    plan = make_plan()

    assert isinstance(
        plan,
        BrowserPlan,
    )

    assert plan.goal == "Get pricing"

    assert plan.site == "https://example.com"

    assert len(plan.steps) == 3


# ==========================================================
# STEP ORDER
# ==========================================================


def test_plan_step_order():

    plan = make_plan()

    assert [
        step.action
        for step in plan.steps
    ] == [
        "navigate",
        "search",
        "extract",
    ]


def test_plan_step_ids_are_sequential():

    plan = make_plan()

    assert [
        step.step_id
        for step in plan.steps
    ] == [
        1,
        2,
        3,
    ]


# ==========================================================
# VALID PLAN
# ==========================================================


def test_valid_plan():

    plan = make_plan()

    PerSitePlanner._validate_plan(
        plan=plan,
        goal="Get pricing",
        site="https://example.com",
    )


# ==========================================================
# INVALID GOAL
# ==========================================================


def test_invalid_goal():

    plan = make_plan()

    with pytest.raises(ValueError):

        PerSitePlanner._validate_plan(
            plan=plan,
            goal="Find products",
            site="https://example.com",
        )


# ==========================================================
# INVALID SITE
# ==========================================================


def test_invalid_site():

    plan = make_plan()

    with pytest.raises(ValueError):

        PerSitePlanner._validate_plan(
            plan=plan,
            goal="Get pricing",
            site="https://wrong-site.com",
        )


# ==========================================================
# EMPTY PLAN
# ==========================================================


def test_empty_plan():

    with pytest.raises(ValueError):

        BrowserPlan(
            goal="Get pricing",
            site="https://example.com",
            steps=[],
        )


# ==========================================================
# NON-SEQUENTIAL STEPS
# ==========================================================


def test_non_sequential_steps():

    plan = make_plan()

    plan.steps[1].step_id = 5

    with pytest.raises(ValueError):

        PerSitePlanner._validate_plan(
            plan=plan,
            goal="Get pricing",
            site="https://example.com",
        )


# ==========================================================
# INVALID ACTION
# ==========================================================


def test_invalid_action():

    with pytest.raises(ValueError):

        PlanStep(
            step_id=1,
            action="click",
            description="Click the pricing button",
            target="pricing",
            expected_result="Pricing page opened",
        )


# ==========================================================
# EMPTY DESCRIPTION
# ==========================================================


def test_empty_description():

    plan = make_plan()

    plan.steps[1].description = "   "

    with pytest.raises(ValueError):

        PerSitePlanner._validate_plan(
            plan=plan,
            goal="Get pricing",
            site="https://example.com",
        )


# ==========================================================
# EXTRACT MUST BE FINAL STEP
# ==========================================================


def test_extract_must_be_final_step():

    plan = BrowserPlan(
        goal="Get pricing",
        site="https://example.com",
        steps=[
            PlanStep(
                step_id=1,
                action="navigate",
                description="Navigate to the website",
                target="https://example.com",
                expected_result="Homepage loaded",
            ),
            PlanStep(
                step_id=2,
                action="extract",
                description="Extract pricing information",
                target="pricing",
                expected_result="Pricing extracted",
            ),
            PlanStep(
                step_id=3,
                action="search",
                description="Search for additional pricing details",
                target="enterprise pricing",
                expected_result="Enterprise pricing found",
            ),
        ],
    )

    with pytest.raises(ValueError):

        PerSitePlanner._validate_plan(
            plan=plan,
            goal="Get pricing",
            site="https://example.com",
        )


# ==========================================================
# VALID PLAN WITHOUT EXTRACT
# ==========================================================


def test_navigation_only_plan():

    plan = BrowserPlan(
        goal="Open website",
        site="https://example.com",
        steps=[
            PlanStep(
                step_id=1,
                action="navigate",
                description="Navigate to the website",
                target="https://example.com",
                expected_result="Homepage loaded",
            ),
        ],
    )

    PerSitePlanner._validate_plan(
        plan=plan,
        goal="Open website",
        site="https://example.com",
    )