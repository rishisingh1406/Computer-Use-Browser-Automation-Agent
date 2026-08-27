import os

import pytest

from app.agent.models import BrowserPlan
from app.agent.planner import PerSitePlanner


# ==========================================================
# REAL LLM PRICING PLANNER
# ==========================================================


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not configured",
)
async def test_real_pricing_planner():

    planner = PerSitePlanner()

    plan = await planner.plan(
        goal="Get pricing",
        site="https://example.com",
    )

    # ------------------------------------------------------
    # Basic plan validation
    # ------------------------------------------------------

    assert isinstance(
        plan,
        BrowserPlan,
    )

    assert plan.goal == "Get pricing"

    assert plan.site == "https://example.com"

    assert len(plan.steps) >= 3

    # ------------------------------------------------------
    # Step ordering
    # ------------------------------------------------------

    assert [
        step.step_id
        for step in plan.steps
    ] == list(
        range(
            1,
            len(plan.steps) + 1,
        )
    )

    # ------------------------------------------------------
    # Expected high-level workflow
    # ------------------------------------------------------

    actions = [
        step.action
        for step in plan.steps
    ]

    assert actions[0] == "navigate"

    assert "search" in actions

    assert "extract" in actions

    # ------------------------------------------------------
    # Extraction should be the final step
    # ------------------------------------------------------

    assert actions[-1] == "extract"

    # ------------------------------------------------------
    # Every step must have a description
    # ------------------------------------------------------

    for step in plan.steps:

        assert step.description.strip()

    # ------------------------------------------------------
    # Print generated plan for inspection
    # ------------------------------------------------------

    print("\nGenerated pricing plan:")

    for step in plan.steps:

        print(
            f"{step.step_id}. "
            f"[{step.action}] "
            f"{step.description}"
        )

        if step.target:
            print(
                f"   Target: {step.target}"
            )

        if step.expected_result:
            print(
                f"   Expected: "
                f"{step.expected_result}"
            )


# ==========================================================
# REAL SITE-SPECIFIC PLANNER
# ==========================================================


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not configured",
)
async def test_site_specific_planner():

    planner = PerSitePlanner()

    plan = await planner.plan(
        goal="Get GitHub Copilot pricing",
        site="https://github.com",
    )

    # ------------------------------------------------------
    # Basic plan validation
    # ------------------------------------------------------

    assert isinstance(
        plan,
        BrowserPlan,
    )

    assert (
        plan.goal
        == "Get GitHub Copilot pricing"
    )

    assert (
        plan.site
        == "https://github.com"
    )

    assert len(plan.steps) >= 2

    # ------------------------------------------------------
    # Step IDs
    # ------------------------------------------------------

    assert [
        step.step_id
        for step in plan.steps
    ] == list(
        range(
            1,
            len(plan.steps) + 1,
        )
    )

    # ------------------------------------------------------
    # High-level actions
    # ------------------------------------------------------

    actions = [
        step.action
        for step in plan.steps
    ]

    assert actions[0] == "navigate"

    assert "extract" in actions

    # ------------------------------------------------------
    # Extraction should be final
    # ------------------------------------------------------

    assert actions[-1] == "extract"

    # ------------------------------------------------------
    # Every step must be valid
    # ------------------------------------------------------

    for step in plan.steps:

        assert step.description.strip()

        assert step.action in {
            "navigate",
            "search",
            "extract",
        }

    # ------------------------------------------------------
    # Print generated plan
    # ------------------------------------------------------

    print("\nGenerated GitHub plan:")

    for step in plan.steps:

        print(
            f"{step.step_id}. "
            f"[{step.action}] "
            f"{step.description}"
        )

        if step.target:
            print(
                f"   Target: {step.target}"
            )

        if step.expected_result:
            print(
                f"   Expected: "
                f"{step.expected_result}"
            )