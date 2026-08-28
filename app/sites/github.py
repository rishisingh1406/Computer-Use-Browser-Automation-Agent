from app.extraction.pricing import PricingExtractor
from app.extraction.schemas import PricingTable


class GitHubPricingHandler:
    """
    Site-specific handler for GitHub Copilot pricing.
    """

    SITE = "github.com"

    PRICING_URL = (
        "https://github.com/features/copilot/plans"
    )

    def __init__(self):
        self.extractor = PricingExtractor()

    def extract_pricing(
        self,
        text: str,
    ) -> PricingTable:

        return self.extractor.extract(
            site=self.SITE,
            product="GitHub Copilot",
            text=text,
        )