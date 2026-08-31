import pytest


class MockBrowserTools:
    def __init__(self):
        self.actions = []

    async def type_text(
        self,
        selector: str,
        text: str,
    ):
        self.actions.append(
            {
                "action": "type",
                "selector": selector,
                "text": text,
            }
        )

    async def click(
        self,
        selector: str,
    ):
        self.actions.append(
            {
                "action": "click",
                "selector": selector,
            }
        )

        return {
            "status": "clicked",
        }


@pytest.fixture
def mock_browser_tools():
    return MockBrowserTools()