from sqlalchemy.orm import Session

from app.database.models import (
    PricingPlanModel,
    PricingTableModel,
)
from app.extraction.schemas import PricingTable


class PricingRepository:
    """
    Handles persistence of normalized pricing data.

    The repository knows about PostgreSQL.

    PricingExtractor does not.
    """

    def __init__(self, session: Session):
        self.session = session

    def save(
        self,
        pricing_table: PricingTable,
    ) -> PricingTableModel:
        """
        Persist one normalized PricingTable and all
        associated PricingPlan records.
        """

        table_model = PricingTableModel(
            site=pricing_table.site,
            product=pricing_table.product,
            currency=pricing_table.currency,
        )

        for plan in pricing_table.plans:
            plan_model = PricingPlanModel(
                name=plan.name,
                price=plan.price,
                currency=plan.currency,
                billing_period=plan.billing_period,
                description=plan.description,
            )

            table_model.plans.append(plan_model)

        self.session.add(table_model)

        try:
            self.session.commit()
            self.session.refresh(table_model)
        except Exception:
            self.session.rollback()
            raise

        return table_model

    def get_all(self) -> list[PricingTableModel]:
        """
        Return all stored pricing tables.
        """
        return (
            self.session
            .query(PricingTableModel)
            .all()
        )

    def get_by_site(
        self,
        site: str,
    ) -> PricingTableModel | None:
        """
        Return the latest pricing table for a site.
        """
        return (
            self.session
            .query(PricingTableModel)
            .filter(
                PricingTableModel.site == site
            )
            .order_by(
                PricingTableModel.created_at.desc()
            )
            .first()
        )