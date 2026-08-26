import pytest

from app.agent.grounding import VisionGrounder


@pytest.mark.asyncio
async def test_visual_grounding():

    grounder = VisionGrounder()

    result = await grounder.locate(
        screenshot_path="screenshots/example.png",
        description="the Learn More link",
    )

    print("\nGROUNDING RESULT:")
    print(result)

    assert result.found is True
    assert result.x is not None
    assert result.y is not None

    assert result.x >= 0
    assert result.y >= 0