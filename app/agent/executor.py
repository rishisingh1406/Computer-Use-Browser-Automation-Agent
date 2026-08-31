from app.agent.models import BrowserAction
from app.browser.tools import BrowserTools
from app.security.guardrails import (
    DomainGuard,
    HumanConfirmationGate,
)


class ActionExecutor:
    """
    Executes BrowserAction objects.

    Security responsibilities:

        1. Validate navigation against DomainGuard.
        2. Inspect clickable elements before execution.
        3. Validate link destinations.
        4. Require human confirmation for submit-type actions.
        5. Validate the final URL after navigation/click.
        6. Keep browser execution separate from LLM decision-making.
    """

    def __init__(
        self,
        browser_tools: BrowserTools,
        domain_guard: DomainGuard | None = None,
        confirmation_gate: HumanConfirmationGate | None = None,
    ):
        self.browser_tools = browser_tools

        self.domain_guard = domain_guard

        self.confirmation_gate = (
            confirmation_gate
            or HumanConfirmationGate()
        )

    async def execute(
        self,
        action: BrowserAction,
    ) -> dict:

        if not isinstance(action, BrowserAction):
            raise TypeError(
                "ActionExecutor.execute expects a BrowserAction."
            )

        # ======================================================
        # NAVIGATE
        # ======================================================

        if action.action == "navigate":

            if not action.url:
                raise ValueError(
                    "navigate requires a URL"
                )

            # --------------------------------------------------
            # PRE-NAVIGATION DOMAIN GUARD
            # --------------------------------------------------

            if self.domain_guard:
                self.domain_guard.validate(
                    action.url
                )

            # --------------------------------------------------
            # EXECUTE NAVIGATION
            # --------------------------------------------------

            result = await self.browser_tools.navigate(
                action.url
            )

            # --------------------------------------------------
            # POST-NAVIGATION DOMAIN CHECK
            # --------------------------------------------------

            final_url = result.get("url")

            if (
                self.domain_guard
                and final_url
            ):
                self.domain_guard.validate(
                    final_url
                )

            return result

        # ======================================================
        # CLICK
        # ======================================================

        if action.action == "click":

            if not action.selector:
                raise ValueError(
                    "click requires a selector"
                )

            # --------------------------------------------------
            # PRE-CHECK ELEMENT
            # --------------------------------------------------

            element_info = (
                await self.browser_tools.inspect_selector(
                    action.selector
                )
            )

            # --------------------------------------------------
            # DOMAIN CHECK FOR LINK
            # --------------------------------------------------

            href = element_info.get("href")

            if (
                href
                and self.domain_guard
            ):
                self.domain_guard.validate(
                    href
                )

            # --------------------------------------------------
            # SUBMIT DETECTION
            # --------------------------------------------------

            if element_info.get(
                "submit_type"
            ):

                approved = (
                    await self.confirmation_gate.confirm(
                        action="click",
                        url=self.browser_tools.page.url,
                        description=(
                            element_info.get(
                                "description"
                            )
                            or action.selector
                        ),
                    )
                )

                if not approved:
                    return {
                        "action": "click",
                        "selector": action.selector,
                        "status": "blocked",
                        "reason": (
                            "Human confirmation denied "
                            "submit-type action."
                        ),
                    }

            # --------------------------------------------------
            # EXECUTE CLICK
            # --------------------------------------------------

            result = await self.browser_tools.click(
                action.selector
            )

            # --------------------------------------------------
            # POST-CLICK DOMAIN CHECK
            # --------------------------------------------------

            final_url = result.get("url")

            if (
                self.domain_guard
                and final_url
            ):
                self.domain_guard.validate(
                    final_url
                )

            return result

        # ======================================================
        # TYPE
        # ======================================================

        if action.action == "type":

            if not action.selector:
                raise ValueError(
                    "type requires a selector"
                )

            if action.text is None:
                raise ValueError(
                    "type requires text"
                )

            return await self.browser_tools.type_text(
                action.selector,
                action.text,
            )

        # ======================================================
        # SCROLL
        # ======================================================

        if action.action == "scroll":

            if not action.direction:
                raise ValueError(
                    "scroll requires a direction"
                )

            if action.direction not in {
                "up",
                "down",
            }:
                raise ValueError(
                    "scroll direction must be 'up' or 'down'"
                )

            return await self.browser_tools.scroll(
                action.direction
            )

        # ======================================================
        # DONE
        # ======================================================

        if action.action == "done":

            return {
                "action": "done",
                "status": "complete",
            }

        # ======================================================
        # UNSUPPORTED ACTION
        # ======================================================

        raise ValueError(
            f"Unsupported action: {action.action}"
        )