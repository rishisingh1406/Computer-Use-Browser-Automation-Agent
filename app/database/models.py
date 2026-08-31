from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class PricingTableModel(Base):
    """
    Database representation of one extracted pricing table.
    """

    __tablename__ = "pricing_tables"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    site: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    product: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    plans: Mapped[list["PricingPlanModel"]] = relationship(
        back_populates="pricing_table",
        cascade="all, delete-orphan",
    )


class PricingPlanModel(Base):
    """
    Database representation of one normalized pricing plan.
    """

    __tablename__ = "pricing_plans"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    pricing_table_id: Mapped[int] = mapped_column(
        ForeignKey(
            "pricing_tables.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )

    billing_period: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    pricing_table: Mapped[PricingTableModel] = relationship(
        back_populates="plans",
    )