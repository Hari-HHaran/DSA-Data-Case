"""Growth Intelligence: forecast runs/results/evaluations, opportunities and sales follow-ups."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._common import created_at_col, updated_at_col


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    window_start: Mapped[str] = mapped_column(String(7))
    window_end: Mapped[str] = mapped_column(String(7))
    selected_model: Mapped[str] = mapped_column(String(40))
    notes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = created_at_col()


class ForecastResult(Base):
    __tablename__ = "forecast_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id", ondelete="CASCADE"), index=True)
    country_code: Mapped[str] = mapped_column(String(2))
    product_family: Mapped[str] = mapped_column(String(1))
    model: Mapped[str] = mapped_column(String(40))
    period: Mapped[str] = mapped_column(String(7))
    kind: Mapped[str] = mapped_column(String(10))  # BACKTEST | FUTURE
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted: Mapped[float] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper: Mapped[float | None] = mapped_column(Float, nullable=True)


class ForecastEvaluation(Base):
    __tablename__ = "forecast_evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(20))  # ALL | FAM-<F> | <CC>-<F>
    # Units differ by family, so MAE is only stored where units are homogeneous (null for ALL).
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    wape: Mapped[float | None] = mapped_column(Float, nullable=True)
    bias: Mapped[float] = mapped_column(Float)
    n_points: Mapped[int] = mapped_column(Integer)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)


class CommercialOpportunity(Base):
    __tablename__ = "commercial_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    opp_key: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(30), index=True)  # CROSS_SELL | INACTIVITY | GROWTH_MARKET | DEMAND_CHANGE
    title: Mapped[str] = mapped_column(String(200))
    insight: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)
    priority_score: Mapped[float] = mapped_column(Float)
    priority_label: Mapped[str] = mapped_column(String(10))
    priority_reason: Mapped[str] = mapped_column(Text, default="")
    customer_master_id: Mapped[int | None] = mapped_column(ForeignKey("master_records.id"), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    product_family: Mapped[str | None] = mapped_column(String(1), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # NEW | UNDER_REVIEW | ASSIGNED | IN_PROGRESS | COMPLETED | DISMISSED
    status: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    owner: Mapped["User | None"] = relationship(lazy="joined")  # noqa: F821
    customer: Mapped["MasterRecord | None"] = relationship(lazy="joined")  # noqa: F821


class SalesFollowup(Base):
    __tablename__ = "sales_followups"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("commercial_opportunities.id", ondelete="CASCADE"), index=True)
    assigned_to_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN | IN_PROGRESS | DONE
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    assigned_to: Mapped["User"] = relationship(foreign_keys=[assigned_to_id], lazy="joined")  # noqa: F821
