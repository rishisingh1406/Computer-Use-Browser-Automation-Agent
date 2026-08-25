import pytest

from app.browser.manager import BrowserManager
from app.browser.tools import BrowserTools


@pytest.fixture
async def browser_tools():
    manager = BrowserManager(headless=True)

    page = await manager.start()

    tools = BrowserTools(page)

    yield tools

    await manager.close()


@pytest.mark.asyncio
async def test_navigate(browser_tools):

    result = await browser_tools.navigate(
        "https://example.com"
    )

    assert result["status"] == 200
    assert result["url"] == "https://example.com/"
    assert result["title"] == "Example Domain"


@pytest.mark.asyncio
async def test_read_text(browser_tools):

    await browser_tools.navigate(
        "https://example.com"
    )

    result = await browser_tools.read_text()

    assert "Example Domain" in result["text"]
    assert "documentation examples" in result["text"]


@pytest.mark.asyncio
async def test_screenshot(browser_tools, tmp_path):

    await browser_tools.navigate(
        "https://example.com"
    )

    screenshot_path = tmp_path / "page.png"

    result = await browser_tools.screenshot(
        str(screenshot_path)
    )

    assert result["action"] == "screenshot"
    assert screenshot_path.exists()


@pytest.mark.asyncio
async def test_click(browser_tools):

    await browser_tools.navigate(
        "https://example.com"
    )

    result = await browser_tools.click(
        "a"
    )

    assert result["action"] == "click"
    assert "iana.org" in result["url"]


@pytest.mark.asyncio
async def test_type_text(browser_tools):

    await browser_tools.navigate(
        "https://www.google.com"
    )

    result = await browser_tools.type_text(
        "textarea[name='q']",
        "Playwright browser automation",
    )

    assert result["action"] == "type"
    assert result["text_length"] > 0


@pytest.mark.asyncio
async def test_scroll(browser_tools):

    await browser_tools.navigate(
        "https://example.com"
    )

    result = await browser_tools.scroll(
        "down"
    )

    assert result["action"] == "scroll"
    assert result["direction"] == "down"
